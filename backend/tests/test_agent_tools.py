import httpx
import pytest

from app.agents.tools import AgentToolError, execute_agent_tool, list_agent_tools
from app.agents.tools.date_tool import DateInfoTool
from app.agents.tools.place_tool import PlaceSearchTool
from app.agents.tools.poi_store import PoiStore
from app.agents.tools.poi_types import VerifiedPoi
from app.agents.tools.weather_tool import WeatherForecastTool
from app.config import settings


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakePoiStore:
    def __init__(self) -> None:
        self.cache: dict[str, list[VerifiedPoi]] = {}
        self.saved: list[tuple[str, list[VerifiedPoi]]] = []
        self.usage: dict[tuple[str, str, str], int] = {}
        self.chunks: list[dict] = []

    def get_cached(self, cache_key: str):
        return self.cache.get(cache_key)

    def save_cache(self, *, cache_key, provider, city, query, pois, raw_json, ttl_days) -> None:
        del provider, raw_json, ttl_days
        self.cache[cache_key] = pois
        self.saved.append((cache_key, pois))
        for poi in pois:
            self.chunks.append({
                "provider_place_id": poi.provider_place_id,
                "poi_name": poi.name,
                "city": city,
                "chunk_text": f"{poi.name} {poi.address} {' '.join(poi.tags)} {query}",
                "tags_json": " ".join(poi.tags),
            })

    def search_chunks(self, *, city, query, tags, limit):
        del query, tags
        return [chunk for chunk in self.chunks if chunk["city"] == city][:limit]

    def get_usage(self, provider, api_name, period_key):
        return self.usage.get((provider, api_name, period_key), 0)

    def increment_usage(self, provider, api_name, period_key):
        key = (provider, api_name, period_key)
        self.usage[key] = self.usage.get(key, 0) + 1
        return self.usage[key]


def test_date_info_tool_returns_requested_date() -> None:
    result = DateInfoTool().run({"travel_date": "2026-06-05", "timezone": "Asia/Shanghai"})

    assert result.status == "success"
    assert result.data["travel_date"] == "2026-06-05"
    assert "Current date" in result.content


def test_weather_forecast_tool_uses_open_meteo(monkeypatch) -> None:
    calls = []

    def fake_get(url, *, params, timeout):
        calls.append((url, params, timeout))
        if "geocoding-api" in url:
            return _FakeResponse({
                "results": [
                    {"name": "Beijing", "country": "China", "latitude": 39.9, "longitude": 116.4}
                ]
            })
        return _FakeResponse({
            "current": {"temperature_2m": 22, "wind_speed_10m": 8},
            "daily": {
                "time": ["2026-06-05"],
                "temperature_2m_max": [28],
                "temperature_2m_min": [18],
                "precipitation_probability_max": [20],
                "weather_code": [1],
            },
        })

    monkeypatch.setattr("app.agents.tools.weather_tool.httpx.get", fake_get)

    result = WeatherForecastTool().run({"city": "Beijing", "travel_date": "2026-06-05", "language": "en"})

    assert result.status == "success"
    assert result.data["provider"] == "open_meteo"
    assert result.data["daily"]["date"] == "2026-06-05"
    assert "18 C to 28 C" in result.content
    assert calls[0][1]["name"] == "Beijing"
    assert calls[1][1]["latitude"] == 39.9


def test_weather_forecast_tool_returns_error_when_city_missing() -> None:
    result = WeatherForecastTool().run({"city": ""})

    assert result.status == "error"
    assert result.data["reason"] == "missing_city"


def test_weather_forecast_tool_handles_http_error(monkeypatch) -> None:
    def fake_get(url, *, params, timeout):
        del url, params, timeout
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr("app.agents.tools.weather_tool.httpx.get", fake_get)

    result = WeatherForecastTool().run({"city": "Beijing"})

    assert result.status == "error"
    assert "Weather service request failed" in result.content


def test_unknown_agent_tool_is_rejected() -> None:
    with pytest.raises(AgentToolError):
        execute_agent_tool("unknown_tool", {})


def test_agent_tools_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_agent_tools_enabled", False)

    assert list_agent_tools() == []
    with pytest.raises(AgentToolError):
        execute_agent_tool("date_info", {})


def test_place_search_uses_amap_and_caches_verified_pois(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_agent_poi_enabled", True)
    monkeypatch.setattr(settings, "amap_web_service_key", "amap-key")
    monkeypatch.setattr(settings, "baidu_map_web_service_ak", "")
    monkeypatch.setattr(settings, "ai_agent_poi_dual_verify_enabled", False)
    store = _FakePoiStore()
    calls = []

    def fake_get(url, *, params, timeout):
        del timeout
        calls.append((url, params))
        return _FakeResponse({
            "status": "1",
            "pois": [
                {
                    "id": "A1",
                    "name": "Bund Riverside Terrace",
                    "cityname": "Shanghai",
                    "address": "No. 1 Riverside Road",
                    "location": "121.4900,31.2400",
                    "type": "Scenic;Night view",
                    "tag": "proposal;photo",
                }
            ],
        })

    monkeypatch.setattr("app.agents.tools.place_tool.httpx.get", fake_get)

    result = PlaceSearchTool(store=store).run({
        "city": "Shanghai",
        "query": "proposal place",
        "intent_tags": ["night view"],
        "language": "en",
        "limit": 3,
    })

    assert result.status == "success"
    assert len(result.data["verified_pois"]) == 1
    assert result.data["verified_pois"][0]["provider"] == "amap"
    assert result.data["verified_pois"][0]["verification_status"] == "single_verified"
    assert store.saved
    assert calls[0][1]["key"] == "amap-key"


def test_place_search_falls_back_to_baidu_when_amap_quota_exceeded(monkeypatch) -> None:
    monkeypatch.setattr(settings, "amap_web_service_key", "amap-key")
    monkeypatch.setattr(settings, "baidu_map_web_service_ak", "baidu-ak")
    monkeypatch.setattr(settings, "ai_agent_poi_amap_monthly_limit", 0)
    monkeypatch.setattr(settings, "ai_agent_poi_baidu_place_daily_limit", 100)
    store = _FakePoiStore()
    calls = []

    def fake_get(url, *, params, timeout):
        del timeout
        calls.append((url, params))
        return _FakeResponse({
            "status": 0,
            "results": [
                {
                    "uid": "B1",
                    "name": "West Lake Lawn",
                    "city": "Hangzhou",
                    "address": "West Lake Scenic Area",
                    "location": {"lat": 30.25, "lng": 120.15},
                    "detail_info": {"tag": "scenic;quiet"},
                }
            ],
        })

    monkeypatch.setattr("app.agents.tools.place_tool.httpx.get", fake_get)

    result = PlaceSearchTool(store=store).run({
        "city": "Hangzhou",
        "query": "quiet proposal place",
        "limit": 3,
    })

    assert result.status == "success"
    assert result.data["fallback_used"] is True
    assert result.data["verified_pois"][0]["provider"] == "baidu"
    assert "baidu" in calls[0][0]


def test_place_search_dual_verifies_amap_with_baidu(monkeypatch) -> None:
    monkeypatch.setattr(settings, "amap_web_service_key", "amap-key")
    monkeypatch.setattr(settings, "baidu_map_web_service_ak", "baidu-ak")
    monkeypatch.setattr(settings, "ai_agent_poi_dual_verify_enabled", True)
    store = _FakePoiStore()

    def fake_get(url, *, params, timeout):
        del timeout
        if "amap" in url:
            return _FakeResponse({
                "status": "1",
                "pois": [
                    {
                        "id": "A2",
                        "name": "Sky Proposal Deck",
                        "cityname": "Shanghai",
                        "address": "88 Tower Road",
                        "location": "121.5000,31.2300",
                        "type": "Observation deck",
                        "tag": "proposal",
                    }
                ],
            })
        return _FakeResponse({
            "status": 0,
            "results": [
                {
                    "uid": "B2",
                    "name": "Sky Proposal Deck",
                    "city": "Shanghai",
                    "address": "88 Tower Road",
                    "location": {"lat": 31.2301, "lng": 121.5001},
                    "detail_info": {"tag": "proposal;view"},
                }
            ],
        })

    monkeypatch.setattr("app.agents.tools.place_tool.httpx.get", fake_get)

    result = PlaceSearchTool(store=store).run({"city": "Shanghai", "query": "proposal", "limit": 3})

    assert result.status == "success"
    poi = result.data["verified_pois"][0]
    assert poi["verification_status"] == "dual_verified"
    assert poi["source_providers"] == ["amap", "baidu"]


def test_place_search_cache_hit_does_not_consume_provider_usage() -> None:
    store = _FakePoiStore()
    store.cache["amap|shanghai|proposal|"] = [
        VerifiedPoi(
            provider="amap",
            provider_place_id="A3",
            name="Cached Place",
            city="Shanghai",
            address="Cached address",
            lat=31.2,
            lng=121.4,
        )
    ]

    result = PlaceSearchTool(store=store).run({"city": "Shanghai", "query": "proposal", "limit": 1})

    assert result.status == "success"
    assert result.data["verified_pois"][0]["name"] == "Cached Place"
    assert store.usage == {}


def test_poi_store_rag_chunks_are_created_only_from_verified_pois() -> None:
    store = PoiStore()
    store._mysql_available = False
    store.save_cache(
        cache_key="test-cache",
        provider="amap",
        city="Shanghai",
        query="proposal",
        pois=[
            VerifiedPoi(
                provider="amap",
                provider_place_id="A4",
                name="Verified Terrace",
                city="Shanghai",
                address="Riverside",
                lat=31.2,
                lng=121.4,
                tags=["proposal"],
            )
        ],
        raw_json={},
        ttl_days=30,
    )

    chunks = store.search_chunks(city="Shanghai", query="proposal", tags=["proposal"], limit=5)

    assert len(chunks) == 1
    assert chunks[0]["provider_place_id"] == "A4"
