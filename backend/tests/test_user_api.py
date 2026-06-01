from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.data_source import reset_data_source_cache
from app.main import app
from app.services import reset_search_service_cache, reset_user_service_cache


def _fresh_client() -> TestClient:
    reset_search_service_cache()
    reset_data_source_cache()
    reset_user_service_cache()
    return TestClient(app)


def _unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid4().hex[:10]}@example.com"


def _register(client: TestClient, email: str | None = None) -> tuple[dict, dict]:
    email = email or _unique_email()
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "tester", "email": email, "password": "secret123"},
    )
    assert response.status_code == 200
    payload = response.json()
    return payload, {"Authorization": f"Bearer {payload['access_token']}"}


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _route_payload() -> dict:
    return {
        "id": "route_test",
        "total_price": 100,
        "total_duration_minutes": 60,
        "transfer_count": 0,
        "legs": [
            {
                "transport_type": "train",
                "from_city": "北京",
                "to_city": "上海",
                "from_city_en": "Beijing",
                "to_city_en": "Shanghai",
                "from_station": "北京南站",
                "to_station": "上海虹桥站",
                "from_station_en": "Beijing South Railway Station",
                "to_station_en": "Shanghai Hongqiao Railway Station",
                "departure_date": "2026-05-18",
                "departure_time": "08:00",
                "arrival_date": "2026-05-18",
                "arrival_time": "09:00",
                "duration_minutes": 60,
                "price": 100,
                "company": "中国铁路",
                "flight_train_no": "G1",
                "platform": "12306",
            }
        ],
    }


def test_auth_profile_and_logout_flow() -> None:
    client = _fresh_client()
    payload, headers = _register(client)

    assert payload["user"]["email"].endswith("@example.com")
    assert payload["session_duration"] == "day"
    expires_at = _parse_datetime(payload["expires_at"])
    created_at = _parse_datetime(payload["user"]["created_at"])
    assert timedelta(hours=23, minutes=59) <= expires_at - created_at <= timedelta(days=1, minutes=1)
    profile_response = client.get("/api/v1/user/profile", headers=headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["username"] == "tester"

    assert client.get("/api/v1/user/profile").status_code == 401
    assert client.post(
        "/api/v1/auth/register",
        json={"username": "dupe", "email": payload["user"]["email"], "password": "secret123"},
    ).status_code == 409

    logout_response = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 200
    assert client.get("/api/v1/user/profile", headers=headers).status_code == 401


def test_auth_session_duration_options() -> None:
    client = _fresh_client()
    email = _unique_email("duration")
    _register(client, email)

    expected_deltas = {
        "day": timedelta(days=1),
        "week": timedelta(days=7),
        "month": timedelta(days=30),
        "half_year": timedelta(days=180),
        "year": timedelta(days=365),
    }
    for duration, expected_delta in expected_deltas.items():
        before = datetime.utcnow()
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "secret123", "session_duration": duration},
        )
        after = datetime.utcnow()
        assert response.status_code == 200
        payload = response.json()
        assert payload["session_duration"] == duration
        expires_at = _parse_datetime(payload["expires_at"])
        assert before + expected_delta <= expires_at <= after + expected_delta + timedelta(seconds=2)

    forever_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123", "session_duration": "forever"},
    )
    assert forever_response.status_code == 200
    assert forever_response.json()["session_duration"] == "forever"
    assert forever_response.json()["expires_at"] is None


def test_expired_auth_token_is_rejected(monkeypatch) -> None:
    from app.services import user_service as user_service_module

    base_time = datetime(2026, 1, 1, 12, 0, 0)
    monkeypatch.setattr(user_service_module, "_utcnow", lambda: base_time)
    client = _fresh_client()
    _, headers = _register(client, _unique_email("expired"))

    monkeypatch.setattr(user_service_module, "_utcnow", lambda: base_time + timedelta(days=1, seconds=1))
    assert client.get("/api/v1/user/profile", headers=headers).status_code == 401


def test_delete_account_removes_user_and_invalidates_token() -> None:
    client = _fresh_client()
    email = _unique_email("delete")
    _, headers = _register(client, email)

    response = client.delete("/api/v1/user/account", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert client.get("/api/v1/user/profile", headers=headers).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    ).status_code == 401


def test_password_reset_preferences_and_import_platforms() -> None:
    client = _fresh_client()
    email = _unique_email("prefs")
    _, headers = _register(client, email)

    assert client.post(
        "/api/v1/auth/forgot-password/check-email",
        json={"email": email},
    ).json() == {"registered": True}
    send_response = client.post(
        "/api/v1/auth/forgot-password/send-code",
        json={"email": email},
    )
    assert send_response.status_code == 200
    assert send_response.json()["expires_in_seconds"] == 60

    verify_response = client.post(
        "/api/v1/auth/forgot-password/verify-code",
        json={"email": email, "code": "000000"},
    )
    assert verify_response.status_code == 200
    reset_token = verify_response.json()["reset_token"]
    assert reset_token
    reset_response = client.post(
        "/api/v1/auth/forgot-password/reset",
        json={"reset_token": reset_token, "new_password": "newsecret123"},
    )
    assert reset_response.status_code == 200
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "newsecret123"},
    ).status_code == 200

    preferences = client.put(
        "/api/v1/user/preferences",
        headers=headers,
        json={"theme": "dark", "language": "en", "chat_retention_days": -1},
    )
    assert preferences.status_code == 200
    assert preferences.json()["theme"] == "dark"
    assert preferences.json()["chat_retention_days"] == -1

    platforms = client.put(
        "/api/v1/user/import-platforms",
        headers=headers,
        json={"platform_key": "platform12306", "enabled": True},
    )
    assert platforms.status_code == 200
    assert platforms.json()["platforms"]["platform12306"] is True


def test_favorites_devices_bookings_and_ai_session_metadata(monkeypatch) -> None:
    def fake_respond(self, *, conversation, draft_request, cities, language="zh"):
        return type(
            "Turn",
            (),
            {
                "assistant_message": "请补充出发城市和日期。",
                "extracted_request": {"to_city": "上海"},
                "should_confirm": False,
                "summary": "目的地上海。",
            },
        )()

    monkeypatch.setattr("app.services.ai_agent.DeepSeekChatClient.respond", fake_respond)

    client = _fresh_client()
    email = _unique_email("full")
    _, first_headers = _register(client, email)
    login_payload = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    ).json()
    second_headers = {"Authorization": f"Bearer {login_payload['access_token']}"}

    devices = client.get("/api/v1/user/devices", headers=second_headers)
    assert devices.status_code == 200
    stale_device = next(device for device in devices.json()["devices"] if not device["is_current"])
    assert client.delete(
        f"/api/v1/user/devices/{stale_device['id']}",
        headers=second_headers,
    ).status_code == 200
    assert client.get("/api/v1/user/profile", headers=first_headers).status_code == 401

    favorite_response = client.post(
        "/api/v1/user/favorites",
        headers=second_headers,
        json={"route": _route_payload()},
    )
    assert favorite_response.status_code == 200
    assert client.post(
        "/api/v1/user/favorites",
        headers=second_headers,
        json={"route": _route_payload()},
    ).status_code == 409
    favorites = client.get("/api/v1/user/favorites", headers=second_headers)
    assert favorites.status_code == 200
    assert favorites.json()["total"] == 1
    assert client.delete(
        "/api/v1/user/favorites/route_test",
        headers=second_headers,
    ).status_code == 200

    booking = client.post(
        "/api/v1/bookings",
        headers=second_headers,
        json={"route_id": "route_test", "legs": _route_payload()["legs"]},
    )
    assert booking.status_code == 200
    assert booking.json()["status"] == "created"

    ai_response = client.post(
        "/api/v1/search/ai/sessions",
        headers=second_headers,
        json={"message": "我想去上海"},
    )
    assert ai_response.status_code == 200
    session_id = ai_response.json()["session_id"]
    sessions = client.get("/api/v1/search/ai/sessions", headers=second_headers)
    assert sessions.status_code == 200
    assert sessions.json()["sessions"][0]["session_id"] == session_id

    renamed = client.put(
        f"/api/v1/search/ai/sessions/{session_id}",
        headers=second_headers,
        json={"title": "上海行程"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "上海行程"
    assert client.delete(
        f"/api/v1/search/ai/sessions/{session_id}",
        headers=second_headers,
    ).status_code == 200
