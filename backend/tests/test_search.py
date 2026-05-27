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
    assert payload["planner_backend"] in {"python", "cpp"}
    assert payload["ai_search_backend"]


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


def test_search_supports_price_and_transport_filters() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "CD",
            "travel_date": "2026-04-22",
            "optimization_target": "price",
            "preferred_transport_types": ["train"],
            "max_price": 800,
            "max_transfers": 0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == 1
    route = payload["routes"][0]
    assert route["total_price"] <= 800
    assert all(leg["transport_type"] == "train" for leg in route["legs"])


def test_search_supports_transfer_city_constraints() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "CD",
            "travel_date": "2026-04-22",
            "optimization_target": "balanced",
            "required_transfer_cities": ["XA"],
            "excluded_cities": ["WH", "NJ", "SH"],
            "max_transfers": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] == 1
    route = payload["routes"][0]
    transfer_cities = {leg["to_city"] for leg in route["legs"][:-1]}
    assert transfer_cities == {"西安"}


def test_search_supports_time_window_filters() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "CD",
            "travel_date": "2026-04-22",
            "optimization_target": "balanced",
            "departure_time_range": {"start": "08:00", "end": "08:30"},
            "arrival_time_range": {"start": "10:30", "end": "20:00"},
            "max_transfers": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] >= 1
    for route in payload["routes"]:
        first_leg = route["legs"][0]
        last_leg = route["legs"][-1]
        assert "08:00" <= first_leg["departure_time"] <= "08:30"
        assert "10:30" <= last_leg["arrival_time"] <= "20:00"


def _mock_deepseek_multi_turn(monkeypatch) -> None:
    def fake_respond(self, *, conversation, draft_request, cities, language="zh"):
        last_message = conversation[-1].content
        if "预算1300" in last_message:
            return type(
                "Turn",
                (),
                {
                    "assistant_message": "我已整理好条件：北京到成都，2026-04-22出发，只坐飞机，预算1300元以内。请确认是否开始搜索？",
                    "extracted_request": {
                        "from_city": "北京",
                        "to_city": "成都",
                        "travel_date": "2026-04-22",
                        "preferred_transport_types": ["flight"],
                        "max_price": 1300,
                        "optimization_target": "price",
                        "max_transfers": 0,
                    },
                    "should_confirm": True,
                    "summary": "已确认出发地、日期、预算和交通偏好。",
                },
            )()

        return type(
            "Turn",
            (),
            {
                "assistant_message": "可以，先告诉我你从哪个城市出发、哪天走。如果你有预算或交通方式偏好，也可以一起说。",
                "extracted_request": {
                    "to_city": "成都",
                    "optimization_target": "price",
                },
                "should_confirm": False,
                "summary": "已识别目的地成都和价格优先偏好。",
            },
        )()

    monkeypatch.setattr(
        "app.services.ai_agent.DeepSeekChatClient.respond",
        fake_respond,
    )


def test_ai_search_collects_fields_across_turns_and_executes_on_confirm(monkeypatch) -> None:
    _mock_deepseek_multi_turn(monkeypatch)
    client = _fresh_client()
    create_response = client.post(
        "/api/v1/search/ai/sessions",
        json={"message": "我想去成都，越便宜越好"},
    )

    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["status"] == "collecting"
    assert create_payload["search_executed"] is False
    assert "from_city" in create_payload["missing_fields"]
    assert "travel_date" in create_payload["missing_fields"]
    assert create_payload["parsed_request"]["to_city"] == "成都"
    assert create_payload["ready_for_confirmation"] is False
    assert create_payload["search_response"] is None

    session_id = create_payload["session_id"]
    message_response = client.post(
        f"/api/v1/search/ai/sessions/{session_id}/messages",
        json={"message": "我从北京出发，2026-04-22走，只坐飞机，预算1300元以内"},
    )

    assert message_response.status_code == 200
    message_payload = message_response.json()
    assert message_payload["status"] == "awaiting_confirmation"
    assert message_payload["missing_fields"] == []
    assert message_payload["ready_for_confirmation"] is True
    assert message_payload["final_request"]["from_city"] == "北京"
    assert message_payload["final_request"]["to_city"] == "成都"
    assert message_payload["final_request"]["preferred_transport_types"] == ["flight"]
    assert message_payload["final_request"]["max_price"] == 1300
    assert message_payload["search_executed"] is False

    confirm_response = client.post(
        f"/api/v1/search/ai/sessions/{session_id}/confirm",
        json={"confirmed": True},
    )

    assert confirm_response.status_code == 200
    confirm_payload = confirm_response.json()
    assert confirm_payload["status"] == "completed"
    assert confirm_payload["search_executed"] is True
    route = confirm_payload["search_response"]["routes"][0]
    assert route["total_price"] <= 1300
    assert all(leg["transport_type"] == "flight" for leg in route["legs"])


def test_ai_search_can_continue_after_user_rejects_confirmation(monkeypatch) -> None:
    _mock_deepseek_multi_turn(monkeypatch)
    client = _fresh_client()
    create_response = client.post(
        "/api/v1/search/ai/sessions",
        json={"message": "我想去成都，越便宜越好"},
    )
    session_id = create_response.json()["session_id"]

    client.post(
        f"/api/v1/search/ai/sessions/{session_id}/messages",
        json={"message": "我从北京出发，2026-04-22走，只坐飞机，预算1300元以内"},
    )
    reject_response = client.post(
        f"/api/v1/search/ai/sessions/{session_id}/confirm",
        json={"confirmed": False},
    )

    assert reject_response.status_code == 200
    reject_payload = reject_response.json()
    assert reject_payload["status"] == "collecting"
    assert reject_payload["search_executed"] is False
    assert "继续调整条件" in reject_payload["assistant_message"]
