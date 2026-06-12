from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from threading import Lock
from typing import Optional
from urllib.parse import unquote, urlparse

from app.config import settings
from app.agents.search_agent_models import AgentModelUsage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_mysql_url(url: str) -> dict:
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "database": (parsed.path or "/layover_lens").lstrip("/"),
    }


@dataclass(frozen=True)
class TokenUsageRecord:
    user_id: str
    session_id: str
    request_id: str
    call_type: str
    usage: AgentModelUsage


class TokenUsageRecorder:
    def __init__(self) -> None:
        self._mysql_config = _parse_mysql_url(settings.database_url)
        self._lock = Lock()
        self._memory_records: list[TokenUsageRecord] = []
        self._mysql_available = self._initialize_mysql()

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

    def _initialize_mysql(self) -> bool:
        try:
            connection = self._connect()
        except Exception:
            return False
        try:
            cursor = connection.cursor()
            cursor.execute(TOKEN_USAGE_TABLE_SQL)
            connection.commit()
            return True
        except Exception:
            return False
        finally:
            connection.close()

    def record(
        self,
        *,
        user_id: str,
        session_id: str,
        request_id: str,
        call_type: str,
        usage: Optional[AgentModelUsage],
    ) -> None:
        if not settings.ai_agent_token_usage_tracking_enabled:
            return
        usage = usage or AgentModelUsage(
            provider="unknown",
            model="unknown",
            usage_unavailable=True,
        )
        record = TokenUsageRecord(
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            call_type=call_type,
            usage=usage,
        )
        if self._mysql_available:
            try:
                self._record_mysql(record)
                return
            except Exception:
                # The first create-session model call may happen before the
                # ai_search_sessions row is inserted. Keep MySQL enabled for
                # subsequent calls and preserve this record in memory.
                pass
        with self._lock:
            self._memory_records.append(record)

    def _record_mysql(self, record: TokenUsageRecord) -> None:
        usage = record.usage
        with self._connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO ai_agent_token_usage (
                    user_id, session_id, request_id, call_type, provider, model,
                    input_tokens, output_tokens, total_tokens, cached_input_tokens,
                    uncached_input_tokens, cache_hit_ratio, raw_usage_json,
                    usage_unavailable, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    record.user_id,
                    record.session_id,
                    record.request_id,
                    record.call_type,
                    usage.provider,
                    usage.model,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.total_tokens,
                    usage.cached_input_tokens,
                    usage.uncached_input_tokens,
                    usage.cache_hit_ratio,
                    json.dumps(usage.raw_usage_json, ensure_ascii=False),
                    usage.usage_unavailable,
                    _utcnow(),
                ),
            )
            connection.commit()

    def aggregate_by_provider_day(self) -> list[dict]:
        if self._mysql_available:
            try:
                with self._connect() as connection:
                    cursor = connection.cursor(dictionary=True)
                    cursor.execute(
                        """
                        SELECT DATE(created_at) AS usage_date, provider, model, call_type,
                               SUM(input_tokens) AS input_tokens,
                               SUM(output_tokens) AS output_tokens,
                               SUM(total_tokens) AS total_tokens,
                               SUM(cached_input_tokens) AS cached_input_tokens,
                               SUM(uncached_input_tokens) AS uncached_input_tokens,
                               AVG(cache_hit_ratio) AS cache_hit_ratio
                        FROM ai_agent_token_usage
                        GROUP BY DATE(created_at), provider, model, call_type
                        ORDER BY usage_date DESC, provider, model, call_type
                        LIMIT 200
                        """
                    )
                    return [dict(row) for row in cursor.fetchall()]
            except Exception:
                self._mysql_available = False
        with self._lock:
            return [
                {
                    "usage_date": record.usage.raw_usage_json.get("date"),
                    "provider": record.usage.provider,
                    "model": record.usage.model,
                    "call_type": record.call_type,
                    "input_tokens": record.usage.input_tokens,
                    "output_tokens": record.usage.output_tokens,
                    "total_tokens": record.usage.total_tokens,
                    "cached_input_tokens": record.usage.cached_input_tokens,
                    "uncached_input_tokens": record.usage.uncached_input_tokens,
                    "cache_hit_ratio": record.usage.cache_hit_ratio,
                }
                for record in self._memory_records[-200:]
            ]


TOKEN_USAGE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ai_agent_token_usage (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(40) NOT NULL,
    session_id VARCHAR(80) NOT NULL,
    request_id VARCHAR(100) NOT NULL,
    call_type VARCHAR(40) NOT NULL,
    provider VARCHAR(80) NOT NULL,
    model VARCHAR(120) NOT NULL,
    input_tokens INT NULL,
    output_tokens INT NULL,
    total_tokens INT NULL,
    cached_input_tokens INT NULL,
    uncached_input_tokens INT NULL,
    cache_hit_ratio DECIMAL(10,6) NULL,
    raw_usage_json TEXT NOT NULL,
    usage_unavailable BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ai_token_user_time (user_id, created_at),
    INDEX idx_ai_token_provider_time (provider, model, created_at),
    INDEX idx_ai_token_session (session_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES ai_search_sessions(session_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


@lru_cache
def get_token_usage_recorder() -> TokenUsageRecorder:
    return TokenUsageRecorder()


def reset_token_usage_recorder_cache() -> None:
    get_token_usage_recorder.cache_clear()
