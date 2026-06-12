from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from threading import Lock
from urllib.parse import unquote, urlparse

from app.config import settings
from app.agents.tools.poi_types import VerifiedPoi


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_mysql_url(url: str) -> dict:
    parsed = urlparse(url.replace("mysql+mysqlconnector://", "mysql://", 1))
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "database": parsed.path.lstrip("/") or "layover_lens",
    }


class PoiStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._memory_cache: dict[str, tuple[list[dict], datetime]] = {}
        self._memory_chunks: dict[str, list[dict]] = {}
        self._memory_usage: dict[tuple[str, str, str], int] = {}
        self._mysql_config = _parse_mysql_url(settings.database_url)
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
            collation="utf8mb4_unicode_ci",
        )

    def _initialize_mysql(self) -> bool:
        try:
            import mysql.connector  # noqa: F401

            with self._connect() as connection:
                cursor = connection.cursor()
                for statement in _TABLES:
                    cursor.execute(statement)
                connection.commit()
            return True
        except Exception:
            return False

    def get_cached(self, cache_key: str) -> list[VerifiedPoi] | None:
        now = _utcnow()
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    "SELECT normalized_json, expires_at FROM poi_cache WHERE cache_key = %s",
                    (cache_key,),
                )
                row = cursor.fetchone()
            if not row or row["expires_at"] <= now:
                return None
            return [_poi_from_dict(item) for item in json.loads(row["normalized_json"])]
        with self._lock:
            item = self._memory_cache.get(cache_key)
            if not item:
                return None
            payload, expires_at = item
            if expires_at <= now:
                self._memory_cache.pop(cache_key, None)
                return None
            return [_poi_from_dict(poi) for poi in payload]

    def save_cache(
        self,
        *,
        cache_key: str,
        provider: str,
        city: str,
        query: str,
        pois: list[VerifiedPoi],
        raw_json: dict,
        ttl_days: int,
    ) -> None:
        expires_at = _utcnow() + timedelta(days=max(ttl_days, 1))
        normalized = [poi.to_dict() for poi in pois]
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO poi_cache (
                        cache_key, provider, city, query_text, normalized_json, raw_json, expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        normalized_json = VALUES(normalized_json),
                        raw_json = VALUES(raw_json),
                        expires_at = VALUES(expires_at),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        cache_key,
                        provider,
                        city,
                        query,
                        json.dumps(normalized, ensure_ascii=False),
                        json.dumps(raw_json, ensure_ascii=False),
                        expires_at,
                    ),
                )
                self._replace_chunks(cursor, cache_key, pois, city, query)
                connection.commit()
            return
        with self._lock:
            self._memory_cache[cache_key] = (normalized, expires_at)
            self._memory_chunks[cache_key] = [_chunk_dict(cache_key, poi, city, query) for poi in pois]

    def search_chunks(self, *, city: str, query: str, tags: list[str], limit: int) -> list[dict]:
        terms = _terms([city, query, *tags])
        if not terms:
            return []
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT cache_key, provider_place_id, poi_name, city, chunk_text, tags_json
                    FROM poi_rag_chunks
                    WHERE city = %s
                    ORDER BY updated_at DESC
                    LIMIT 200
                    """,
                    (city,),
                )
                chunks = cursor.fetchall()
        else:
            with self._lock:
                chunks = [chunk for values in self._memory_chunks.values() for chunk in values if chunk["city"] == city]
        scored = []
        for chunk in chunks:
            text = " ".join([
                str(chunk.get("poi_name", "")),
                str(chunk.get("chunk_text", "")),
                str(chunk.get("tags_json", "")),
            ]).lower()
            score = sum(2 if term in text else 0 for term in terms)
            score += sum(1 for term in terms if any(part.startswith(term) for part in text.split()))
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def get_usage(self, provider: str, api_name: str, period_key: str) -> int:
        key = (provider, api_name, period_key)
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    "SELECT call_count FROM poi_provider_usage WHERE provider = %s AND api_name = %s AND period_key = %s",
                    key,
                )
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        return self._memory_usage.get(key, 0)

    def increment_usage(self, provider: str, api_name: str, period_key: str) -> int:
        key = (provider, api_name, period_key)
        if self._mysql_available:
            with self._connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    """
                    INSERT INTO poi_provider_usage (provider, api_name, period_key, call_count)
                    VALUES (%s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE call_count = call_count + 1, updated_at = CURRENT_TIMESTAMP
                    """,
                    key,
                )
                connection.commit()
                return self.get_usage(provider, api_name, period_key)
        with self._lock:
            self._memory_usage[key] = self._memory_usage.get(key, 0) + 1
            return self._memory_usage[key]

    @staticmethod
    def _replace_chunks(cursor, cache_key: str, pois: list[VerifiedPoi], city: str, query: str) -> None:
        cursor.execute("DELETE FROM poi_rag_chunks WHERE cache_key = %s", (cache_key,))
        for poi in pois:
            chunk = _chunk_dict(cache_key, poi, city, query)
            cursor.execute(
                """
                INSERT INTO poi_rag_chunks (
                    cache_key, provider, provider_place_id, poi_name, city, chunk_text, tags_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    cache_key,
                    poi.provider,
                    poi.provider_place_id,
                    poi.name,
                    city,
                    chunk["chunk_text"],
                    chunk["tags_json"],
                ),
            )


def _poi_from_dict(payload: dict) -> VerifiedPoi:
    return VerifiedPoi(
        provider=str(payload.get("provider") or ""),
        provider_place_id=str(payload.get("provider_place_id") or ""),
        name=str(payload.get("name") or ""),
        city=str(payload.get("city") or ""),
        address=str(payload.get("address") or ""),
        lat=float(payload.get("lat") or 0),
        lng=float(payload.get("lng") or 0),
        categories=list(payload.get("categories") or []),
        tags=list(payload.get("tags") or []),
        verification_status=str(payload.get("verification_status") or "single_verified"),
        source_providers=list(payload.get("source_providers") or [payload.get("provider") or ""]),
    )


def _chunk_dict(cache_key: str, poi: VerifiedPoi, city: str, query: str) -> dict:
    tags = sorted(set([*poi.tags, *poi.categories, query]))
    return {
        "cache_key": cache_key,
        "provider": poi.provider,
        "provider_place_id": poi.provider_place_id,
        "poi_name": poi.name,
        "city": city,
        "chunk_text": " ".join([poi.name, poi.city, poi.address, " ".join(tags)]),
        "tags_json": json.dumps(tags, ensure_ascii=False),
    }


def _terms(values: list[str]) -> list[str]:
    output = []
    for value in values:
        for part in str(value or "").lower().replace(",", " ").split():
            if part and part not in output:
                output.append(part)
        value_text = str(value or "").strip().lower()
        if value_text and value_text not in output:
            output.append(value_text)
    return output


_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS poi_cache (
        cache_key VARCHAR(255) PRIMARY KEY,
        provider VARCHAR(40) NOT NULL,
        city VARCHAR(120) NOT NULL,
        query_text VARCHAR(255) NOT NULL,
        normalized_json MEDIUMTEXT NOT NULL,
        raw_json MEDIUMTEXT NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_poi_cache_city_query (city, query_text),
        INDEX idx_poi_cache_expires (expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS poi_rag_chunks (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        cache_key VARCHAR(255) NOT NULL,
        provider VARCHAR(40) NOT NULL,
        provider_place_id VARCHAR(120) NOT NULL,
        poi_name VARCHAR(255) NOT NULL,
        city VARCHAR(120) NOT NULL,
        chunk_text TEXT NOT NULL,
        tags_json TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_poi_rag_city (city),
        INDEX idx_poi_rag_cache (cache_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS poi_provider_usage (
        provider VARCHAR(40) NOT NULL,
        api_name VARCHAR(60) NOT NULL,
        period_key VARCHAR(20) NOT NULL,
        call_count INT NOT NULL DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (provider, api_name, period_key)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]
