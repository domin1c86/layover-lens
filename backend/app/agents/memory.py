from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from threading import Lock
from typing import Optional
from urllib.parse import unquote, urlparse

from app.config import settings
from app.schemas import AgentMemoryEntry, ParsedSearchRequest


MEMORY_SOURCE = "agent_rule"
TRAVEL_STYLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("romantic", ("romantic", "proposal", "honeymoon", "anniversary", "求婚", "蜜月", "纪念日", "浪漫")),
    ("family", ("family", "child", "kid", "parent", "亲子", "家人", "父母", "孩子")),
    ("quiet", ("quiet", "relax", "restorative", "安静", "放松", "休闲", "疗愈")),
    ("scenic", ("scenic", "view", "nature", "mountain", "sea", "风景", "自然", "山", "海")),
    ("budget", ("budget", "cheap", "low cost", "省钱", "便宜", "低预算")),
)


@dataclass(frozen=True)
class MemoryMutation:
    memory_key: str
    memory_value: dict


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


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_json(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        loaded = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


class AgentMemoryService:
    def __init__(self) -> None:
        self._mysql_config = _parse_mysql_url(settings.database_url)
        self._memory: dict[str, dict[str, AgentMemoryEntry]] = {}
        self._lock = Lock()
        self._mysql_available = self._initialize_mysql()

    def _ensure_mysql_available(self) -> bool:
        if self._mysql_available:
            return True
        self._mysql_available = self._initialize_mysql()
        return self._mysql_available

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
            cursor.execute(AGENT_MEMORY_TABLE_SQL)
            connection.commit()
            return True
        except Exception:
            return False
        finally:
            connection.close()

    def list_memories(self, user_id: str) -> list[AgentMemoryEntry]:
        if not settings.ai_agent_long_term_memory_enabled:
            return []
        if self._ensure_mysql_available():
            try:
                with self._connect() as connection:
                    cursor = connection.cursor(dictionary=True)
                    cursor.execute(
                        """
                        SELECT memory_key, memory_value_json, confidence, evidence_count,
                               source, last_seen_at, updated_at
                        FROM ai_agent_user_memory
                        WHERE user_id = %s
                        ORDER BY confidence DESC, evidence_count DESC, updated_at DESC
                        LIMIT %s
                        """,
                        (user_id, max(1, settings.ai_agent_memory_max_items)),
                    )
                    return [self._entry_from_row(row) for row in cursor.fetchall()]
            except Exception:
                self._mysql_available = False
        with self._lock:
            rows = list(self._memory.get(user_id, {}).values())
        return sorted(rows, key=lambda item: (item.confidence, item.evidence_count, item.updated_at), reverse=True)[
            : max(1, settings.ai_agent_memory_max_items)
        ]

    def delete_memory(self, user_id: str, memory_key: str) -> bool:
        if self._ensure_mysql_available():
            try:
                with self._connect() as connection:
                    cursor = connection.cursor()
                    cursor.execute(
                        "DELETE FROM ai_agent_user_memory WHERE user_id = %s AND memory_key = %s",
                        (user_id, memory_key),
                    )
                    connection.commit()
                    return cursor.rowcount > 0
            except Exception:
                self._mysql_available = False
        with self._lock:
            return self._memory.get(user_id, {}).pop(memory_key, None) is not None

    def clear_memories(self, user_id: str) -> None:
        if self._ensure_mysql_available():
            try:
                with self._connect() as connection:
                    cursor = connection.cursor()
                    cursor.execute("DELETE FROM ai_agent_user_memory WHERE user_id = %s", (user_id,))
                    connection.commit()
                    return
            except Exception:
                self._mysql_available = False
        with self._lock:
            self._memory.pop(user_id, None)

    def build_summary(self, user_id: str, *, language: str = "zh") -> str:
        memories = [
            item for item in self.list_memories(user_id)
            if item.confidence >= settings.ai_agent_memory_min_confidence
        ]
        if not memories:
            return ""
        facts = [
            {
                "key": item.memory_key,
                "value": item.memory_value,
                "confidence": round(item.confidence, 3),
                "evidence_count": item.evidence_count,
            }
            for item in memories[: max(1, settings.ai_agent_memory_max_items)]
        ]
        label = "用户长期旅行偏好" if language == "zh" else "User long-term travel preferences"
        return f"{label}: {_json(facts)}"

    def update_from_turn(
        self,
        *,
        user_id: str,
        parsed_request: ParsedSearchRequest,
        message: str = "",
        confirmed_search: bool = False,
    ) -> list[AgentMemoryEntry]:
        if not settings.ai_agent_long_term_memory_enabled:
            return []
        mutations = self._extract_mutations(
            parsed_request=parsed_request,
            message=message,
            confirmed_search=confirmed_search,
        )
        if not mutations:
            return []
        updated: list[AgentMemoryEntry] = []
        for mutation in mutations:
            updated.append(self._upsert_memory(user_id, mutation))
        return updated

    def _extract_mutations(
        self,
        *,
        parsed_request: ParsedSearchRequest,
        message: str,
        confirmed_search: bool,
    ) -> list[MemoryMutation]:
        mutations: list[MemoryMutation] = []
        if parsed_request.from_city:
            mutations.append(MemoryMutation(
                "frequent_departure_city",
                {"city": parsed_request.from_city, "confirmed": confirmed_search},
            ))
        if parsed_request.to_city:
            mutations.append(MemoryMutation(
                "frequent_destination_city",
                {"city": parsed_request.to_city, "confirmed": confirmed_search},
            ))
        for transport in parsed_request.preferred_transport_types or []:
            mutations.append(MemoryMutation(
                f"preferred_transport_type:{transport}",
                {"transport_type": transport, "confirmed": confirmed_search},
            ))
        if parsed_request.optimization_target:
            mutations.append(MemoryMutation(
                f"optimization_target:{parsed_request.optimization_target}",
                {"optimization_target": parsed_request.optimization_target, "confirmed": confirmed_search},
            ))
        if parsed_request.max_price is not None:
            mutations.append(MemoryMutation(
                "budget_ceiling",
                {"max_price": parsed_request.max_price, "confirmed": confirmed_search},
            ))
        for city in parsed_request.excluded_cities or []:
            mutations.append(MemoryMutation(
                f"avoided_city:{city}",
                {"city": city, "confirmed": confirmed_search},
            ))
        for city in parsed_request.required_transfer_cities or []:
            mutations.append(MemoryMutation(
                f"preferred_transfer_city:{city}",
                {"city": city, "confirmed": confirmed_search},
            ))
        lowered = message.lower()
        for style, keywords in TRAVEL_STYLE_KEYWORDS:
            if any(keyword.lower() in lowered for keyword in keywords):
                mutations.append(MemoryMutation(
                    f"travel_style:{style}",
                    {"style": style, "confirmed": confirmed_search},
                ))
        return mutations

    def _upsert_memory(self, user_id: str, mutation: MemoryMutation) -> AgentMemoryEntry:
        now = _utcnow()
        if self._ensure_mysql_available():
            try:
                with self._connect() as connection:
                    cursor = connection.cursor(dictionary=True)
                    cursor.execute(
                        """
                        INSERT INTO ai_agent_user_memory (
                            user_id, memory_key, memory_value_json, confidence,
                            evidence_count, source, last_seen_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            memory_value_json = VALUES(memory_value_json),
                            confidence = LEAST(1.0, confidence + 0.08),
                            evidence_count = evidence_count + 1,
                            source = VALUES(source),
                            last_seen_at = VALUES(last_seen_at),
                            updated_at = VALUES(updated_at)
                        """,
                        (
                            user_id,
                            mutation.memory_key,
                            _json(mutation.memory_value),
                            0.6,
                            1,
                            MEMORY_SOURCE,
                            now,
                            now,
                        ),
                    )
                    connection.commit()
                    cursor.execute(
                        """
                        SELECT memory_key, memory_value_json, confidence, evidence_count,
                               source, last_seen_at, updated_at
                        FROM ai_agent_user_memory
                        WHERE user_id = %s AND memory_key = %s
                        """,
                        (user_id, mutation.memory_key),
                    )
                    row = cursor.fetchone()
                    if row:
                        return self._entry_from_row(row)
            except Exception:
                self._mysql_available = False
        with self._lock:
            user_memories = self._memory.setdefault(user_id, {})
            existing = user_memories.get(mutation.memory_key)
            entry = AgentMemoryEntry(
                memory_key=mutation.memory_key,
                memory_value=mutation.memory_value,
                confidence=min(1.0, (existing.confidence if existing else 0.52) + 0.08),
                evidence_count=(existing.evidence_count if existing else 0) + 1,
                source=MEMORY_SOURCE,
                last_seen_at=now,
                updated_at=now,
            )
            user_memories[mutation.memory_key] = entry
            return entry

    @staticmethod
    def _entry_from_row(row: dict) -> AgentMemoryEntry:
        return AgentMemoryEntry(
            memory_key=str(row["memory_key"]),
            memory_value=_load_json(row.get("memory_value_json")),
            confidence=float(row.get("confidence") or 0.0),
            evidence_count=int(row.get("evidence_count") or 0),
            source=str(row.get("source") or MEMORY_SOURCE),
            last_seen_at=row["last_seen_at"],
            updated_at=row["updated_at"],
        )


AGENT_MEMORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ai_agent_user_memory (
    user_id VARCHAR(40) NOT NULL,
    memory_key VARCHAR(120) NOT NULL,
    memory_value_json TEXT NOT NULL,
    confidence DECIMAL(5,4) NOT NULL DEFAULT 0.6000,
    evidence_count INT NOT NULL DEFAULT 1,
    source VARCHAR(40) NOT NULL DEFAULT 'agent_rule',
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, memory_key),
    INDEX idx_ai_memory_user_updated (user_id, updated_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


@lru_cache
def get_agent_memory_service() -> AgentMemoryService:
    return AgentMemoryService()


def reset_agent_memory_service_cache() -> None:
    get_agent_memory_service.cache_clear()
