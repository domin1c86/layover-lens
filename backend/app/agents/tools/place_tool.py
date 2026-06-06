from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from threading import Lock

import httpx

from app.config import settings
from app.agents.tools.poi_store import PoiStore
from app.agents.tools.poi_types import VerifiedPoi
from app.agents.tools.types import AgentToolResult


class PlaceSearchTool:
    name = "place_search"
    description = (
        "Search real POIs for travel recommendations. Use this for attraction, restaurant, scenic, "
        "proposal, family, nightlife, quiet-place, or place recommendation requests. Returned places "
        "are verified by map providers and must be cited by provider_place_id."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "Chinese city or destination city name"},
            "query": {"type": "string", "description": "Place need, e.g. suitable for proposal"},
            "intent_tags": {"type": "array", "items": {"type": "string"}},
            "language": {"type": "string", "description": "zh or en"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["city", "query"],
    }

    def __init__(self, store: PoiStore | None = None) -> None:
        self._store = store or PoiStore()
        self._qps_lock = Lock()
        self._recent_calls: dict[tuple[str, str], list[float]] = {}

    def run(self, arguments: dict) -> AgentToolResult:
        city = str(arguments.get("city") or "").strip()
        query = str(arguments.get("query") or "").strip()
        language = str(arguments.get("language") or "zh")
        tags = [str(item).strip() for item in arguments.get("intent_tags") or [] if str(item).strip()]
        limit = _clamp_int(arguments.get("limit"), 1, settings.ai_agent_poi_max_results)
        limit = min(limit, settings.ai_agent_poi_max_results)

        if not settings.ai_agent_poi_enabled:
            return self._error("POI search is disabled.", "poi_disabled")
        if not city or not query:
            return self._error("POI search needs both city and query.", "missing_city_or_query")

        primary = settings.ai_agent_poi_primary_provider.strip().lower()
        providers = ["amap", "baidu"] if primary == "amap" else ["baidu", "amap"]
        verified_pois: list[VerifiedPoi] = []
        fallback_used = False
        raw_payloads: dict[str, dict] = {}
        errors: list[str] = []

        for index, provider in enumerate(providers):
            cache_key = _cache_key(provider, city, query, tags, dual_verify=settings.ai_agent_poi_dual_verify_enabled)
            cached = self._store.get_cached(cache_key)
            if cached:
                verified_pois = cached
                fallback_used = index > 0
                break
            try:
                found, raw = self._search_provider(provider, city=city, query=query, tags=tags, limit=max(limit, 5), language=language)
                raw_payloads[provider] = raw
            except PoiProviderError as exc:
                errors.append(str(exc))
                continue
            if not found:
                errors.append(f"{provider} returned no POI.")
                continue
            if settings.ai_agent_poi_dual_verify_enabled and provider == "amap":
                found = self._dual_verify_with_baidu(found, city=city)
            self._store.save_cache(
                cache_key=cache_key,
                provider=provider,
                city=city,
                query=query,
                pois=found,
                raw_json=raw_payloads.get(provider, {}),
                ttl_days=settings.ai_agent_poi_cache_ttl_days,
            )
            verified_pois = found
            fallback_used = index > 0
            break

        if not verified_pois:
            return AgentToolResult(
                name=self.name,
                status="error",
                content="Unable to verify real places with configured map providers.",
                data={
                    "reason": "no_verified_poi",
                    "errors": errors,
                    "provider_usage": self._usage_snapshot(),
                    "verified_pois": [],
                    "fallback_used": fallback_used,
                    "dual_verify_enabled": settings.ai_agent_poi_dual_verify_enabled,
                },
            )

        ranked = self._rank_with_rag(city=city, query=query, tags=tags, pois=verified_pois, limit=limit)
        status_counts = {poi.verification_status for poi in ranked}
        content = f"Verified {len(ranked)} real place(s) in {city} for {query}."
        if "dual_verified" in status_counts:
            content += " Some places were cross-verified by Amap and Baidu."
        return AgentToolResult(
            name=self.name,
            status="success",
            content=content,
            data={
                "verified_pois": [poi.to_dict() for poi in ranked],
                "provider_usage": self._usage_snapshot(),
                "fallback_used": fallback_used,
                "dual_verify_enabled": settings.ai_agent_poi_dual_verify_enabled,
                "rag_chunks": self._store.search_chunks(city=city, query=query, tags=tags, limit=limit),
            },
        )

    def _search_provider(
        self,
        provider: str,
        *,
        city: str,
        query: str,
        tags: list[str],
        limit: int,
        language: str,
    ) -> tuple[list[VerifiedPoi], dict]:
        if provider == "amap":
            return self._search_amap(city=city, query=query, tags=tags, limit=limit)
        if provider == "baidu":
            return self._search_baidu(city=city, query=query, tags=tags, limit=limit, language=language)
        raise PoiProviderError(f"Unsupported POI provider: {provider}")

    def _search_amap(self, *, city: str, query: str, tags: list[str], limit: int) -> tuple[list[VerifiedPoi], dict]:
        if not settings.amap_web_service_key:
            raise PoiProviderError("Amap key is not configured.")
        self._reserve_quota("amap", "place_search", _month_key(), settings.ai_agent_poi_amap_monthly_limit)
        self._enforce_qps("amap", "place_search", settings.ai_agent_poi_amap_qps_limit)
        response = httpx.get(
            "https://restapi.amap.com/v3/place/text",
            params={
                "key": settings.amap_web_service_key,
                "keywords": _query_text(query, tags),
                "city": city,
                "offset": min(limit, 20),
                "page": 1,
                "extensions": "all",
                "output": "json",
            },
            timeout=settings.ai_agent_tool_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("status")) != "1":
            raise PoiProviderError(f"Amap request failed: {payload.get('info') or payload.get('infocode')}")
        pois = []
        for item in payload.get("pois") or []:
            poi = _amap_poi(item)
            if poi:
                pois.append(poi)
        return pois[:limit], payload

    def _search_baidu(self, *, city: str, query: str, tags: list[str], limit: int, language: str) -> tuple[list[VerifiedPoi], dict]:
        del language
        if not settings.baidu_map_web_service_ak:
            raise PoiProviderError("Baidu map key is not configured.")
        self._reserve_quota("baidu", "place_search", _day_key(), settings.ai_agent_poi_baidu_place_daily_limit)
        self._enforce_qps("baidu", "place_search", settings.ai_agent_poi_baidu_place_qps_limit)
        response = httpx.get(
            "https://api.map.baidu.com/place/v2/search",
            params={
                "ak": settings.baidu_map_web_service_ak,
                "query": _query_text(query, tags),
                "region": city,
                "city_limit": "true",
                "page_size": min(limit, 20),
                "page_num": 0,
                "output": "json",
                "scope": 2,
            },
            timeout=settings.ai_agent_tool_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("status", -1)) != 0:
            raise PoiProviderError(f"Baidu place request failed: {payload.get('message') or payload.get('status')}")
        pois = []
        for item in payload.get("results") or []:
            poi = _baidu_poi(item, fallback_city=city)
            if poi:
                pois.append(poi)
        return pois[:limit], payload

    def _dual_verify_with_baidu(self, pois: list[VerifiedPoi], *, city: str) -> list[VerifiedPoi]:
        verified = []
        for poi in pois:
            try:
                candidates, _ = self._search_baidu(city=city, query=poi.name, tags=[], limit=5, language="zh")
            except PoiProviderError:
                verified.append(poi)
                continue
            match = next((candidate for candidate in candidates if _same_place(poi, candidate)), None)
            if match:
                verified.append(VerifiedPoi(
                    provider=poi.provider,
                    provider_place_id=poi.provider_place_id,
                    name=poi.name,
                    city=poi.city,
                    address=poi.address,
                    lat=poi.lat,
                    lng=poi.lng,
                    categories=poi.categories,
                    tags=sorted(set([*poi.tags, *match.tags, *match.categories])),
                    verification_status="dual_verified",
                    source_providers=["amap", "baidu"],
                    raw=poi.raw,
                ))
            else:
                verified.append(poi)
        return verified

    def _rank_with_rag(self, *, city: str, query: str, tags: list[str], pois: list[VerifiedPoi], limit: int) -> list[VerifiedPoi]:
        chunks = self._store.search_chunks(city=city, query=query, tags=tags, limit=100)
        chunk_scores = {str(chunk.get("provider_place_id")): index for index, chunk in enumerate(chunks)}
        terms = _token_set([query, *tags])

        def score(poi: VerifiedPoi) -> tuple[int, int, str]:
            text = " ".join([poi.name, poi.address, " ".join(poi.categories), " ".join(poi.tags)]).lower()
            lexical = sum(1 for term in terms if term in text)
            verify = 3 if poi.verification_status == "dual_verified" else 1
            rag = max(0, 100 - chunk_scores.get(poi.provider_place_id, 100))
            return (verify + lexical + rag, verify, poi.name)

        return sorted(pois, key=score, reverse=True)[:limit]

    def _reserve_quota(self, provider: str, api_name: str, period_key: str, limit: int) -> None:
        if limit <= 0:
            raise PoiProviderError(f"{provider} {api_name} quota is disabled for {period_key}.")
        used = self._store.get_usage(provider, api_name, period_key)
        if used >= limit:
            raise PoiProviderError(f"{provider} {api_name} quota exceeded for {period_key}.")
        self._store.increment_usage(provider, api_name, period_key)

    def _enforce_qps(self, provider: str, api_name: str, qps_limit: int) -> None:
        if qps_limit <= 0:
            raise PoiProviderError(f"{provider} {api_name} QPS is disabled.")
        now = time.monotonic()
        key = (provider, api_name)
        with self._qps_lock:
            calls = [item for item in self._recent_calls.get(key, []) if now - item < 1]
            if len(calls) >= qps_limit:
                raise PoiProviderError(f"{provider} {api_name} QPS limit reached.")
            calls.append(now)
            self._recent_calls[key] = calls

    def _usage_snapshot(self) -> list[dict]:
        return [
            _usage_item("amap", "place_search", _month_key(), settings.ai_agent_poi_amap_monthly_limit, "month", self._store),
            _usage_item("baidu", "place_search", _day_key(), settings.ai_agent_poi_baidu_place_daily_limit, "day", self._store),
            _usage_item("baidu", "geocode", _day_key(), settings.ai_agent_poi_baidu_geocode_daily_limit, "day", self._store),
            _usage_item(
                "baidu",
                "reverse_geocode",
                _day_key(),
                settings.ai_agent_poi_baidu_reverse_geocode_daily_limit,
                "day",
                self._store,
            ),
        ]

    def _error(self, content: str, reason: str) -> AgentToolResult:
        return AgentToolResult(
            name=self.name,
            status="error",
            content=content,
            data={"reason": reason, "verified_pois": [], "provider_usage": self._usage_snapshot()},
        )


class PoiProviderError(RuntimeError):
    pass


def _amap_poi(item: dict) -> VerifiedPoi | None:
    location = str(item.get("location") or "")
    try:
        lng_text, lat_text = location.split(",", 1)
        lng = float(lng_text)
        lat = float(lat_text)
    except ValueError:
        return None
    categories = [part for part in str(item.get("type") or "").split(";") if part]
    tags = [part for part in str(item.get("tag") or "").replace(";", "|").split("|") if part]
    city = str(item.get("cityname") or item.get("adname") or "")
    address = item.get("address")
    return VerifiedPoi(
        provider="amap",
        provider_place_id=str(item.get("id") or ""),
        name=str(item.get("name") or ""),
        city=city,
        address=str(address if isinstance(address, str) else ""),
        lat=lat,
        lng=lng,
        categories=categories,
        tags=tags,
        verification_status="single_verified",
        source_providers=["amap"],
        raw=item,
    )


def _baidu_poi(item: dict, *, fallback_city: str) -> VerifiedPoi | None:
    location = item.get("location") or {}
    try:
        lat = float(location.get("lat"))
        lng = float(location.get("lng"))
    except (TypeError, ValueError):
        return None
    detail = item.get("detail_info") if isinstance(item.get("detail_info"), dict) else {}
    tag_text = str(detail.get("tag") or item.get("tag") or "")
    tags = [part for part in tag_text.replace(";", "|").split("|") if part]
    return VerifiedPoi(
        provider="baidu",
        provider_place_id=str(item.get("uid") or ""),
        name=str(item.get("name") or ""),
        city=str(item.get("city") or fallback_city),
        address=str(item.get("address") or ""),
        lat=lat,
        lng=lng,
        categories=tags,
        tags=tags,
        verification_status="single_verified",
        source_providers=["baidu"],
        raw=item,
    )


def _same_place(left: VerifiedPoi, right: VerifiedPoi) -> bool:
    if _normalize_name(left.name) == _normalize_name(right.name):
        return True
    if _normalize_name(left.name) in _normalize_name(right.name) or _normalize_name(right.name) in _normalize_name(left.name):
        return _distance_m(left.lat, left.lng, right.lat, right.lng) <= 1500
    return _distance_m(left.lat, left.lng, right.lat, right.lng) <= 500


def _distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _normalize_name(value: str) -> str:
    return "".join(str(value or "").lower().split())


def _query_text(query: str, tags: list[str]) -> str:
    unique = []
    for item in [query, *tags]:
        value = str(item or "").strip()
        if value and value not in unique:
            unique.append(value)
    return " ".join(unique)


def _cache_key(provider: str, city: str, query: str, tags: list[str], *, dual_verify: bool) -> str:
    parts = [provider, _normalize_name(city), _normalize_name(query), _normalize_name(" ".join(sorted(tags)))]
    if dual_verify:
        parts.append("dual")
    return "|".join(parts)


def _token_set(values: list[str]) -> set[str]:
    tokens = set()
    for value in values:
        text = str(value or "").lower()
        tokens.add(text)
        tokens.update(part for part in text.replace(",", " ").split() if part)
    tokens.discard("")
    return tokens


def _day_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m")


def _usage_item(provider: str, api_name: str, period_key: str, limit: int, period: str, store: PoiStore) -> dict:
    used = store.get_usage(provider, api_name, period_key)
    return {
        "provider": provider,
        "api": api_name,
        "used": used,
        "remaining": max(limit - used, 0) if limit > 0 else None,
        "limit": limit,
        "period": period,
    }


def _clamp_int(value, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = maximum
    return max(minimum, min(parsed, maximum))
