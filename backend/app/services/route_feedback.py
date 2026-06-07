from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional
from urllib.parse import unquote, urlparse
from uuid import uuid4

from fastapi import status

from app.config import settings
from app.schemas import (
    RouteFeedbackAnnotationRequest,
    RouteFeedbackAnnotationResponse,
    RouteFeedbackCreateRequest,
    RouteFeedbackResponse,
)


class RouteFeedbackError(RuntimeError):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        super().__init__(message)
        self.status_code = status_code


class RouteFeedbackService:
    def __init__(self) -> None:
        self._mysql_config = _parse_database_url(settings.database_url)
        self._mysql_available = self._initialize_mysql()
        self._feedback: dict[str, dict] = {}
        self._annotations: dict[str, dict] = {}

    def create_feedback(self, user_id: Optional[str], payload: RouteFeedbackCreateRequest) -> RouteFeedbackResponse:
        if user_id is None and not payload.anonymous_session_id:
            raise RouteFeedbackError("Anonymous session id is required.", status.HTTP_400_BAD_REQUEST)
        feedback_id = f"feedback_{uuid4().hex}"
        now = datetime.now(timezone.utc)
        record = {
            "id": feedback_id,
            "user_id": user_id,
            "search_id": payload.search_id,
            "recommendation_id": payload.recommendation_id,
            "action": payload.action,
            "anonymous_session_id": payload.anonymous_session_id or "",
            "source": payload.source,
            "feedback_context": payload.feedback_context,
            "ratings_json": _json(payload.ratings.model_dump() if payload.ratings else {}),
            "selected_recommendation_ids_json": _json(payload.selected_recommendation_ids),
            "clicked_provider": payload.clicked_provider or "",
            "clicked_segment_index": payload.clicked_segment_index,
            "comment": payload.comment or "",
            "search_request_json": _json(payload.search_request),
            "recommendation_json": _json(payload.recommendation),
            "model_version": payload.model_version or "",
            "dataset_version": payload.dataset_version or "",
            "created_at": now,
        }
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO route_feedback (
                        id, user_id, search_id, recommendation_id, action,
                        anonymous_session_id, source, feedback_context, ratings_json,
                        selected_recommendation_ids_json, clicked_provider, clicked_segment_index,
                        comment,
                        search_request_json, recommendation_json, model_version,
                        dataset_version, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record["id"],
                        record["user_id"],
                        record["search_id"],
                        record["recommendation_id"],
                        record["action"],
                        record["anonymous_session_id"],
                        record["source"],
                        record["feedback_context"],
                        record["ratings_json"],
                        record["selected_recommendation_ids_json"],
                        record["clicked_provider"],
                        record["clicked_segment_index"],
                        record["comment"],
                        record["search_request_json"],
                        record["recommendation_json"],
                        record["model_version"],
                        record["dataset_version"],
                        record["created_at"].replace(tzinfo=None),
                    ),
                )
                connection.commit()
        else:
            self._feedback[feedback_id] = record
        return RouteFeedbackResponse(id=feedback_id, created_at=now)

    def annotate_feedback(
        self,
        feedback_id: str,
        annotator_user_id: str,
        payload: RouteFeedbackAnnotationRequest,
    ) -> RouteFeedbackAnnotationResponse:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("SELECT id FROM route_feedback WHERE id = %s", (feedback_id,))
                if cursor.fetchone() is None:
                    raise RouteFeedbackError("Feedback not found.", status.HTTP_404_NOT_FOUND)
                now = datetime.now(timezone.utc)
                cursor.execute(
                    """
                    INSERT INTO route_feedback_annotations (
                        feedback_id, annotator_user_id, label, issues_json, notes, annotated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        annotator_user_id = VALUES(annotator_user_id),
                        label = VALUES(label),
                        issues_json = VALUES(issues_json),
                        notes = VALUES(notes),
                        annotated_at = VALUES(annotated_at)
                    """,
                    (
                        feedback_id,
                        annotator_user_id,
                        payload.label,
                        _json(payload.issues),
                        payload.notes or "",
                        now.replace(tzinfo=None),
                    ),
                )
                connection.commit()
        else:
            if feedback_id not in self._feedback:
                raise RouteFeedbackError("Feedback not found.", status.HTTP_404_NOT_FOUND)
            now = datetime.now(timezone.utc)
            self._annotations[feedback_id] = {
                "feedback_id": feedback_id,
                "annotator_user_id": annotator_user_id,
                "label": payload.label,
                "issues": payload.issues,
                "notes": payload.notes or "",
                "annotated_at": now,
            }
        return RouteFeedbackAnnotationResponse(
            feedback_id=feedback_id,
            label=payload.label,
            issues=payload.issues,
            annotated_at=now,
        )

    def export_annotated_samples(self) -> list[dict]:
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT
                        f.id, f.user_id, f.search_id, f.recommendation_id,
                        f.action, f.anonymous_session_id, f.source, f.feedback_context,
                        f.ratings_json, f.selected_recommendation_ids_json,
                        f.clicked_provider, f.clicked_segment_index,
                        f.comment, f.search_request_json,
                        f.recommendation_json, f.model_version, f.dataset_version,
                        a.label, a.issues_json, a.notes, a.annotated_at
                    FROM route_feedback f
                    JOIN route_feedback_annotations a ON a.feedback_id = f.id
                    ORDER BY a.annotated_at DESC
                    """
                )
                return [_sample_from_row(row) for row in cursor.fetchall()]
        return [
            {
                **record,
                "search_request": json.loads(record["search_request_json"] or "{}"),
                "recommendation": json.loads(record["recommendation_json"] or "{}"),
                "annotation": self._annotations[feedback_id],
            }
            for feedback_id, record in self._feedback.items()
            if feedback_id in self._annotations
        ]

    def _initialize_mysql(self) -> bool:
        try:
            import mysql.connector  # noqa: F401
        except ImportError:
            return False
        try:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS route_feedback (
                        id VARCHAR(80) PRIMARY KEY,
                        user_id VARCHAR(64) NULL,
                        search_id VARCHAR(120) NOT NULL,
                        recommendation_id VARCHAR(255) NOT NULL,
                        action VARCHAR(40) NOT NULL,
                        anonymous_session_id VARCHAR(120) NOT NULL DEFAULT '',
                        source VARCHAR(20) NOT NULL DEFAULT 'search',
                        feedback_context VARCHAR(40) NOT NULL DEFAULT 'route_card',
                        ratings_json JSON NOT NULL,
                        selected_recommendation_ids_json JSON NOT NULL,
                        clicked_provider VARCHAR(20) NOT NULL DEFAULT '',
                        clicked_segment_index INT NULL,
                        comment TEXT NULL,
                        search_request_json JSON NOT NULL,
                        recommendation_json JSON NOT NULL,
                        model_version VARCHAR(120) NOT NULL DEFAULT '',
                        dataset_version VARCHAR(120) NOT NULL DEFAULT '',
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_route_feedback_user_time (user_id, created_at),
                        INDEX idx_route_feedback_model (model_version, dataset_version)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
                _ensure_route_feedback_columns(cursor)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS route_feedback_annotations (
                        feedback_id VARCHAR(80) PRIMARY KEY,
                        annotator_user_id VARCHAR(64) NOT NULL,
                        label VARCHAR(40) NOT NULL,
                        issues_json JSON NOT NULL,
                        notes TEXT NULL,
                        annotated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_route_feedback_annotation
                            FOREIGN KEY (feedback_id) REFERENCES route_feedback(id)
                            ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
                connection.commit()
            return True
        except Exception:
            return False

    def _connect(self):
        import mysql.connector

        return mysql.connector.connect(
            host=self._mysql_config["host"],
            port=self._mysql_config["port"],
            user=self._mysql_config["user"],
            password=self._mysql_config["password"],
            database=self._mysql_config["database"],
            charset="utf8mb4",
            collation="utf8mb4_general_ci",
            use_unicode=True,
        )


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _sample_from_row(row: dict) -> dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "search_id": row["search_id"],
        "recommendation_id": row["recommendation_id"],
        "action": row["action"],
        "anonymous_session_id": row.get("anonymous_session_id") or "",
        "source": row.get("source") or "search",
        "feedback_context": row.get("feedback_context") or "route_card",
        "ratings": json.loads(row.get("ratings_json") or "{}"),
        "selected_recommendation_ids": json.loads(row.get("selected_recommendation_ids_json") or "[]"),
        "clicked_provider": row.get("clicked_provider") or "",
        "clicked_segment_index": row.get("clicked_segment_index"),
        "comment": row["comment"] or "",
        "search_request": json.loads(row["search_request_json"] or "{}"),
        "recommendation": json.loads(row["recommendation_json"] or "{}"),
        "model_version": row["model_version"],
        "dataset_version": row["dataset_version"],
        "annotation": {
            "label": row["label"],
            "issues": json.loads(row["issues_json"] or "[]"),
            "notes": row["notes"] or "",
            "annotated_at": row["annotated_at"],
        },
    }


def _ensure_route_feedback_columns(cursor) -> None:
    statements = [
        "ALTER TABLE route_feedback MODIFY user_id VARCHAR(64) NULL",
        "ALTER TABLE route_feedback ADD COLUMN anonymous_session_id VARCHAR(120) NOT NULL DEFAULT '' AFTER action",
        "ALTER TABLE route_feedback ADD COLUMN source VARCHAR(20) NOT NULL DEFAULT 'search' AFTER anonymous_session_id",
        "ALTER TABLE route_feedback ADD COLUMN feedback_context VARCHAR(40) NOT NULL DEFAULT 'route_card' AFTER source",
        "ALTER TABLE route_feedback ADD COLUMN ratings_json JSON NULL AFTER feedback_context",
        "ALTER TABLE route_feedback ADD COLUMN selected_recommendation_ids_json JSON NULL AFTER ratings_json",
        "ALTER TABLE route_feedback ADD COLUMN clicked_provider VARCHAR(20) NOT NULL DEFAULT '' AFTER selected_recommendation_ids_json",
        "ALTER TABLE route_feedback ADD COLUMN clicked_segment_index INT NULL AFTER clicked_provider",
    ]
    for statement in statements:
        try:
            cursor.execute(statement)
        except Exception:
            continue


def _parse_database_url(database_url: str) -> dict:
    parsed = urlparse(database_url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "database": parsed.path.lstrip("/") or "layover_lens",
    }


@lru_cache
def get_route_feedback_service() -> RouteFeedbackService:
    return RouteFeedbackService()


def reset_route_feedback_service_cache() -> None:
    get_route_feedback_service.cache_clear()
