from datetime import datetime, timedelta
import re
from uuid import uuid4

import pyotp
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.data_source import reset_data_source_cache
from app.main import app
from app.agents.search_agent import reset_search_agent_service_cache
from app.services import reset_search_service_cache, reset_user_service_cache


@pytest.fixture(autouse=True)
def _use_legacy_agent_model(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_model_provider", "legacy")
    monkeypatch.setattr(settings, "deepseek_api_key", "")


def _fresh_client() -> TestClient:
    reset_search_service_cache()
    reset_search_agent_service_cache()
    reset_data_source_cache()
    reset_user_service_cache()
    return TestClient(app)


def _unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid4().hex[:10]}@example.com"


def _email_verification_token(client: TestClient, email: str, purpose: str = "register") -> str:
    send_response = client.post(
        "/api/v1/auth/email-verification/send",
        json={"email": email, "purpose": purpose},
    )
    assert send_response.status_code == 200
    assert send_response.json()["expires_in_seconds"] == 60
    verify_response = client.post(
        "/api/v1/auth/email-verification/verify",
        json={"email": email, "purpose": purpose, "code": "000000"},
    )
    assert verify_response.status_code == 200
    token = verify_response.json()["verification_token"]
    assert token
    return token


def _register(client: TestClient, email: str | None = None) -> tuple[dict, dict]:
    email = email or _unique_email()
    verification_token = _email_verification_token(client, email)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "tester",
            "email": email,
            "password": "secret123",
            "email_verification_token": verification_token,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    return payload, {"Authorization": f"Bearer {payload['access_token']}"}


def _csrf_headers(client: TestClient) -> dict[str, str]:
    csrf = client.cookies.get(settings.csrf_cookie_name)
    assert csrf
    return {settings.csrf_header_name: csrf}


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
    assert payload["user"]["email_verified"] is True
    assert re.fullmatch(r"user_\d{14}\d+", payload["user"]["id"])
    assert payload["user"]["username"] == payload["user"]["id"]
    assert payload["user"]["nickname"] == "tester"
    assert payload["session_duration"] == "day"
    expires_at = _parse_datetime(payload["expires_at"])
    created_at = _parse_datetime(payload["user"]["created_at"])
    assert timedelta(hours=23, minutes=59) <= expires_at - created_at <= timedelta(days=1, minutes=1)
    profile_response = client.get("/api/v1/user/profile", headers=headers)
    assert profile_response.status_code == 200
    assert profile_response.json()["username"] == payload["user"]["id"]
    assert profile_response.json()["nickname"] == "tester"
    assert profile_response.json()["email_verified"] is True

    client.cookies.clear()
    assert client.get("/api/v1/user/profile").status_code == 401
    assert client.post(
        "/api/v1/auth/register",
        json={"username": "dupe", "email": payload["user"]["email"], "password": "secret123"},
    ).status_code == 422
    assert client.post(
        "/api/v1/auth/email-verification/send",
        json={"email": payload["user"]["email"], "purpose": "register"},
    ).status_code == 409

    logout_response = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 200
    assert client.get("/api/v1/user/profile", headers=headers).status_code == 401


def test_cookie_auth_and_csrf_flow() -> None:
    client = _fresh_client()
    payload, _ = _register(client, _unique_email("cookie"))

    assert settings.auth_cookie_name in client.cookies
    assert settings.csrf_cookie_name in client.cookies
    profile_response = client.get("/api/v1/user/profile")
    assert profile_response.status_code == 200
    assert profile_response.json()["id"] == payload["user"]["id"]

    missing_csrf = client.put("/api/v1/user/profile", json={"nickname": "No CSRF"})
    assert missing_csrf.status_code == 403

    updated = client.put(
        "/api/v1/user/profile",
        headers=_csrf_headers(client),
        json={"nickname": "Cookie User"},
    )
    assert updated.status_code == 200
    assert updated.json()["nickname"] == "Cookie User"

    logout = client.post("/api/v1/auth/logout", headers=_csrf_headers(client))
    assert logout.status_code == 200
    assert settings.auth_cookie_name not in client.cookies
    assert client.get("/api/v1/user/profile").status_code == 401


def test_login_rate_limit_rejects_repeated_failures() -> None:
    client = _fresh_client()
    email = _unique_email("rate")
    _register(client, email)

    response = None
    for _ in range(7):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "wrong-password"},
        )

    assert response is not None
    assert response.status_code == 429


def test_production_does_not_fallback_to_memory_store(monkeypatch) -> None:
    from app.services import user_service as user_service_module

    monkeypatch.setattr(user_service_module.settings, "app_env", "production")
    monkeypatch.setattr(
        user_service_module.settings,
        "database_url",
        "mysql+mysqlconnector://root:wrong@127.0.0.1:1/missing",
    )

    try:
        user_service_module.UserService()
    except RuntimeError as exc:
        assert "MySQL is required" in str(exc)
    else:
        raise AssertionError("Production user service unexpectedly fell back to memory storage.")


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


def test_register_generates_time_based_user_ids(monkeypatch) -> None:
    from app.services import user_service as user_service_module

    base_time = datetime(2026, 5, 6, 7, 8, 9)
    monkeypatch.setattr(user_service_module, "_utcnow", lambda: base_time)
    client = _fresh_client()

    first, _ = _register(client, _unique_email("same-second-1"))
    second, _ = _register(client, _unique_email("same-second-2"))
    third, _ = _register(client, _unique_email("same-second-3"))

    prefix = "user_20260506150809"
    first_suffix = int(first["user"]["id"].removeprefix(prefix))
    assert first["user"]["id"].startswith(prefix)
    assert second["user"]["id"] == f"{prefix}{first_suffix + 1}"
    assert third["user"]["id"] == f"{prefix}{first_suffix + 2}"
    assert first["user"]["username"] == first["user"]["id"]
    assert first["user"]["nickname"] == "tester"


def test_update_current_session_duration() -> None:
    client = _fresh_client()
    _, headers = _register(client, _unique_email("duration-update"))

    before = datetime.utcnow()
    response = client.put(
        "/api/v1/user/session-duration",
        headers=headers,
        json={"session_duration": "week"},
    )
    after = datetime.utcnow()

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_duration"] == "week"
    expires_at = _parse_datetime(payload["expires_at"])
    assert before + timedelta(days=7) <= expires_at <= after + timedelta(days=7, seconds=2)
    assert client.get("/api/v1/user/profile", headers=headers).status_code == 200

    forever_response = client.put(
        "/api/v1/user/session-duration",
        headers=headers,
        json={"session_duration": "forever"},
    )
    assert forever_response.status_code == 200
    assert forever_response.json()["session_duration"] == "forever"
    assert forever_response.json()["expires_at"] is None


def test_authenticated_use_refreshes_current_device_time(monkeypatch) -> None:
    from app.services import user_service as user_service_module

    base_time = datetime(2026, 1, 1, 9, 0, 0)
    later_time = datetime(2026, 1, 1, 11, 30, 0)
    monkeypatch.setattr(user_service_module, "_utcnow", lambda: base_time)
    client = _fresh_client()
    _, headers = _register(client, _unique_email("device-touch"))

    monkeypatch.setattr(user_service_module, "_utcnow", lambda: later_time)
    assert client.get("/api/v1/user/profile", headers=headers).status_code == 200
    devices = client.get("/api/v1/user/devices", headers=headers)

    assert devices.status_code == 200
    current_device = next(device for device in devices.json()["devices"] if device["is_current"])
    assert _parse_datetime(current_device["login_time"]) == later_time


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


def test_update_avatar_preset_updates_profile() -> None:
    client = _fresh_client()
    _, headers = _register(client, _unique_email("avatar"))

    response = client.put(
        "/api/v1/user/avatar/preset",
        headers=headers,
        json={"preset_id": "m1"},
    )

    assert response.status_code == 200
    assert response.json()["avatar_url"] == "material:m1"
    profile = client.get("/api/v1/user/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["avatar_url"] == "material:m1"


def test_email_verification_change_email_and_password_check() -> None:
    client = _fresh_client()
    email = _unique_email("security")
    _, headers = _register(client, email)

    current_token = _email_verification_token(client, email, "verify_current")
    verify_current = client.post(
        "/api/v1/user/email/verify",
        headers=headers,
        json={"verification_token": current_token},
    )
    assert verify_current.status_code == 200
    assert verify_current.json()["email_verified"] is True

    assert client.post(
        "/api/v1/user/password/check",
        headers=headers,
        json={"current_password": "wrong"},
    ).json() == {"valid": False}
    assert client.post(
        "/api/v1/user/password/check",
        headers=headers,
        json={"current_password": "secret123"},
    ).json() == {"valid": True}

    registered_email = _unique_email("registered")
    _register(client, registered_email)
    assert client.post(
        "/api/v1/auth/email-verification/send",
        json={"email": registered_email, "purpose": "change_email"},
    ).status_code == 409

    new_email = _unique_email("changed")
    change_token = _email_verification_token(client, new_email, "change_email")
    bad_update = client.put(
        "/api/v1/user/email",
        headers=headers,
        json={
            "current_email": "wrong@example.com",
            "new_email": new_email,
            "verification_token": change_token,
        },
    )
    assert bad_update.status_code == 400

    change_token = _email_verification_token(client, new_email, "change_email")
    update = client.put(
        "/api/v1/user/email",
        headers=headers,
        json={
            "current_email": email,
            "new_email": new_email,
            "verification_token": change_token,
        },
    )
    assert update.status_code == 200
    assert update.json()["email"] == new_email
    assert update.json()["email_verified"] is True

    assert client.put(
        "/api/v1/user/password",
        headers=headers,
        json={"current_password": "wrong", "new_password": "nextsecret123"},
    ).status_code == 400
    assert client.put(
        "/api/v1/user/password",
        headers=headers,
        json={"current_password": "secret123", "new_password": "nextsecret123"},
    ).status_code == 200
    assert client.post(
        "/api/v1/auth/login",
        json={"email": new_email, "password": "nextsecret123"},
    ).status_code == 200


def test_password_change_revokes_other_devices() -> None:
    client = _fresh_client()
    email = _unique_email("password-revoke")
    _, first_headers = _register(client, email)
    second_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert second_login.status_code == 200
    second_headers = {"Authorization": f"Bearer {second_login.json()['access_token']}"}

    changed = client.put(
        "/api/v1/user/password",
        headers=second_headers,
        json={"current_password": "secret123", "new_password": "nextsecret123"},
    )
    assert changed.status_code == 200
    assert client.get("/api/v1/user/profile", headers=first_headers).status_code == 401
    assert client.get("/api/v1/user/profile", headers=second_headers).status_code == 200


def test_totp_setup_login_challenge_and_disable() -> None:
    client = _fresh_client()
    email = _unique_email("totp")
    _, headers = _register(client, email)

    assert client.put(
        "/api/v1/user/totp/email-code-replacement",
        headers=headers,
        json={"enabled": True},
    ).status_code == 409

    wrong_setup = client.post(
        "/api/v1/user/totp/setup",
        headers=headers,
        json={"current_password": "wrong"},
    )
    assert wrong_setup.status_code == 400

    setup = client.post(
        "/api/v1/user/totp/setup",
        headers=headers,
        json={"current_password": "secret123"},
    )
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert setup.json()["provisioning_uri"].startswith("otpauth://totp/")

    assert client.post(
        "/api/v1/user/totp/enable",
        headers=headers,
        json={"code": "000000"},
    ).status_code == 400

    code = pyotp.TOTP(secret).now()
    enabled = client.post(
        "/api/v1/user/totp/enable",
        headers=headers,
        json={"code": code},
    )
    assert enabled.status_code == 200
    assert enabled.json()["totp_enabled"] is True
    assert enabled.json()["totp_replaces_email_codes"] is False

    replacement = client.put(
        "/api/v1/user/totp/email-code-replacement",
        headers=headers,
        json={"enabled": True},
    )
    assert replacement.status_code == 200
    assert replacement.json()["totp_replaces_email_codes"] is True

    reset_method = client.post(
        "/api/v1/auth/forgot-password/check-email",
        json={"email": email},
    )
    assert reset_method.json() == {"registered": True, "verification_method": "totp"}
    send_reset = client.post(
        "/api/v1/auth/forgot-password/send-code",
        json={"email": email},
    )
    assert send_reset.json() == {"expires_in_seconds": 0, "verification_method": "totp"}
    assert client.post(
        "/api/v1/auth/forgot-password/verify-code",
        json={"email": email, "code": "000000"},
    ).json() == {"verified": False, "reset_token": None}
    totp_reset = client.post(
        "/api/v1/auth/forgot-password/verify-code",
        json={"email": email, "code": pyotp.TOTP(secret).now()},
    )
    assert totp_reset.status_code == 200
    assert totp_reset.json()["verified"] is True
    assert totp_reset.json()["reset_token"]

    client.cookies.clear()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert login.status_code == 200
    assert login.json()["requires_totp"] is True
    assert "access_token" not in login.json()

    challenge_token = login.json()["challenge_token"]
    assert client.post(
        "/api/v1/auth/login/totp",
        json={"challenge_token": challenge_token, "code": "000000"},
    ).status_code == 401

    verified = client.post(
        "/api/v1/auth/login/totp",
        json={"challenge_token": challenge_token, "code": pyotp.TOTP(secret).now()},
    )
    assert verified.status_code == 200
    assert verified.json()["requires_totp"] is False
    assert client.get("/api/v1/user/profile").status_code == 200
    assert client.post(
        "/api/v1/auth/login/totp",
        json={"challenge_token": challenge_token, "code": pyotp.TOTP(secret).now()},
    ).status_code == 401

    disabled = client.post(
        "/api/v1/user/totp/disable",
        headers=headers,
        json={"current_password": "secret123", "code": pyotp.TOTP(secret).now()},
    )
    assert disabled.status_code == 200
    assert disabled.json()["totp_enabled"] is False
    assert disabled.json()["totp_replaces_email_codes"] is False
    assert client.post(
        "/api/v1/auth/forgot-password/reset",
        json={"reset_token": totp_reset.json()["reset_token"], "new_password": "should-not-apply"},
    ).status_code == 400
    assert client.post(
        "/api/v1/auth/forgot-password/check-email",
        json={"email": email},
    ).json() == {"registered": True, "verification_method": "email"}


def test_password_reset_preferences_and_import_platforms() -> None:
    client = _fresh_client()
    email = _unique_email("prefs")
    _, headers = _register(client, email)

    assert client.post(
        "/api/v1/auth/forgot-password/check-email",
        json={"email": email},
    ).json() == {"registered": True, "verification_method": "email"}
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
                "assistant_message": "Please provide the departure city and travel date.",
                "extracted_request": {"to_city": "上海"},
                "should_confirm": False,
                "summary": "Destination Shanghai.",
            },
        )()

    monkeypatch.setattr("app.agents.ai_agent.DeepSeekChatClient.respond", fake_respond)

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
        json={"message": "I want to go to Shanghai."},
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


def test_ai_sessions_require_authentication_and_enforce_ownership(monkeypatch) -> None:
    def fake_respond(self, *, conversation, draft_request, cities, language="zh"):
        return type(
            "Turn",
            (),
            {
                "assistant_message": "Please provide the travel date.",
                "extracted_request": {"from_city": "Beijing", "to_city": "Shanghai"},
                "should_confirm": False,
                "summary": "Beijing to Shanghai.",
            },
        )()

    monkeypatch.setattr("app.agents.ai_agent.DeepSeekChatClient.respond", fake_respond)
    client = _fresh_client()
    assert client.post("/api/v1/search/ai/sessions", json={"message": "Beijing to Shanghai"}).status_code == 401

    _, owner_headers = _register(client, _unique_email("ai-owner"))
    _, other_headers = _register(client, _unique_email("ai-other"))
    created = client.post(
        "/api/v1/search/ai/sessions",
        headers=owner_headers,
        json={"message": "Beijing to Shanghai", "language": "en"},
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    assert client.get(f"/api/v1/search/ai/sessions/{session_id}", headers=other_headers).status_code == 404
    assert client.post(
        f"/api/v1/search/ai/sessions/{session_id}/messages",
        headers=other_headers,
        json={"message": "tomorrow", "language": "en"},
    ).status_code == 404
    assert client.get(f"/api/v1/search/ai/sessions/{session_id}", headers=owner_headers).status_code == 200


def test_ai_stream_returns_ordered_sse_events(monkeypatch) -> None:
    def fake_respond(self, *, conversation, draft_request, cities, language="zh"):
        return type(
            "Turn",
            (),
            {
                "assistant_message": "Please provide the travel date.",
                "extracted_request": {"from_city": "Beijing", "to_city": "Shanghai"},
                "should_confirm": False,
                "summary": "Beijing to Shanghai.",
            },
        )()

    monkeypatch.setattr("app.agents.ai_agent.DeepSeekChatClient.respond", fake_respond)
    client = _fresh_client()
    _, headers = _register(client, _unique_email("ai-stream"))
    response = client.post(
        "/api/v1/search/ai/sessions/stream",
        headers=headers,
        json={"message": "Beijing to Shanghai", "language": "en"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: status" in body
    assert "event: assistant_delta" in body
    assert "event: done" in body
    assert body.index("event: status") < body.index("event: done")


def test_ai_storage_guard_blocks_new_ai_writes(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_agent_storage_disable_new_writes", True)
    client = _fresh_client()
    _, headers = _register(client, _unique_email("ai-storage-guard"))

    response = client.post(
        "/api/v1/search/ai/sessions",
        headers=headers,
        json={"message": "Beijing to Shanghai", "language": "en"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ai_storage_guard_active"

    search_response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "SH",
            "travel_date": "2026-06-05",
            "optimization_target": "balanced",
        },
    )
    assert search_response.status_code == 200
