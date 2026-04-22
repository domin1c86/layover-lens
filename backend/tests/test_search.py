from fastapi.testclient import TestClient

from app.data_source import reset_data_source_cache
from app.main import app
from app.services import reset_search_service_cache


def _fresh_client() -> TestClient:
    reset_search_service_cache()
    reset_data_source_cache()
    return TestClient(app)


def test_health_check() -> None:
    client = _fresh_client()
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_source"].startswith("mock:")


def test_cities_endpoint_returns_seed_data() -> None:
    client = _fresh_client()
    response = client.get("/api/v1/cities")

    assert response.status_code == 200
    payload = response.json()
    assert "cities" in payload
    assert len(payload["cities"]) >= 5
    assert any(city["code"] == "BJ" for city in payload["cities"])


def test_cities_keyword_filter() -> None:
    client = _fresh_client()
    response = client.get("/api/v1/cities", params={"keyword": "北京"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["cities"]) >= 1
    assert all("北京" in city["name"] or city["code"] == "BJ" for city in payload["cities"])


def test_search_endpoint_returns_ranked_routes() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "CD",
            "travel_date": "2026-04-22",
            "optimization_target": "balanced",
            "max_transfers": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] >= 1
    assert payload["total"] == payload["total_count"]
    first_route = payload["routes"][0]
    assert first_route["id"].startswith("route_")
    assert first_route["legs"]
    assert first_route["legs"][0]["transport_type"] in {"flight", "train"}
    assert first_route["legs"][0]["departure_date"] == "2026-04-22"
    assert "arrival_date" in first_route["legs"][0]


def test_search_endpoint_accepts_legacy_alias_fields() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "北京",
            "to_city": "成都",
            "date": "2026-04-22",
            "optimize": "price",
            "filters": {"max_transfer": 1},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    prices = [route["total_price"] for route in payload["routes"]]
    assert prices == sorted(prices)


def test_search_unknown_city_returns_404() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "Moon",
            "to_city": "CD",
            "travel_date": "2026-04-22",
            "optimization_target": "balanced",
        },
    )

    assert response.status_code == 404


def test_search_returns_empty_for_unseeded_date() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "CD",
            "travel_date": "2026-04-30",
            "optimization_target": "balanced",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == 0
    assert payload["routes"] == []
