from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.data_source import reset_data_source_cache
from app.main import app
from app.agents.search_agent import reset_search_agent_service_cache
from app.services import reset_search_service_cache
from app.services.route_feedback import reset_route_feedback_service_cache


@pytest.fixture(autouse=True)
def _use_legacy_agent_model(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_model_provider", "legacy")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "route_dataset_mode", "mock")


def _fresh_client() -> TestClient:
    reset_search_service_cache()
    reset_search_agent_service_cache()
    reset_data_source_cache()
    reset_route_feedback_service_cache()
    return TestClient(app)


def _ai_headers(client: TestClient) -> dict[str, str]:
    email = f"ai-scope-{uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/email-verification/send", json={"email": email, "purpose": "register"})
    verification = client.post(
        "/api/v1/auth/email-verification/verify",
        json={"email": email, "purpose": "register", "code": "000000"},
    ).json()
    payload = client.post(
        "/api/v1/auth/register",
        json={
            "username": "ai-scope-tester",
            "email": email,
            "password": "secret123",
            "email_verification_token": verification["verification_token"],
        },
    ).json()
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_ai_scope_guard_rejects_programming_request_without_search() -> None:
    client = _fresh_client()
    headers = _ai_headers(client)
    response = client.post(
        "/api/v1/search/ai/sessions",
        headers=headers,
        json={"message": "Please write a Python crawler for me.", "language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "collecting_required"
    assert payload["search_executed"] is False
    assert payload["tool_results"] == []
    assert payload["search_response"] is None
    assert "non-travel" in payload["assistant_message"]


def test_ai_scope_guard_allows_destination_discovery() -> None:
    client = _fresh_client()
    headers = _ai_headers(client)
    response = client.post(
        "/api/v1/search/ai/sessions",
        headers=headers,
        json={"message": "I want to travel but do not know where to go.", "language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "collecting_required"
    assert payload["search_executed"] is False
    assert payload["ready_for_confirmation"] is False
    assert "without a fixed destination" in payload["assistant_message"]


def test_ai_scope_guard_allows_travel_context_story() -> None:
    client = _fresh_client()
    headers = _ai_headers(client)
    response = client.post(
        "/api/v1/search/ai/sessions",
        headers=headers,
        json={"message": "I want a meaningful proposal trip but I do not have a destination.", "language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "collecting_required"
    assert payload["search_executed"] is False
    assert "meaningful" in payload["assistant_message"]


def test_ai_scope_guard_blocks_current_session_after_repeated_off_topic_requests() -> None:
    client = _fresh_client()
    headers = _ai_headers(client)
    create_response = client.post(
        "/api/v1/search/ai/sessions",
        headers=headers,
        json={"message": "Write Python code for sorting.", "language": "en"},
    )
    session_id = create_response.json()["session_id"]

    second_response = client.post(
        f"/api/v1/search/ai/sessions/{session_id}/messages",
        headers=headers,
        json={"message": "Debug this React component.", "language": "en"},
    )
    third_response = client.post(
        f"/api/v1/search/ai/sessions/{session_id}/messages",
        headers=headers,
        json={"message": "Generate SQL code for a database.", "language": "en"},
    )

    assert second_response.status_code == 200
    assert third_response.status_code == 200
    blocked_payload = third_response.json()
    assert blocked_payload["status"] == "blocked"
    assert "paused" in blocked_payload["assistant_message"]

    append_after_block = client.post(
        f"/api/v1/search/ai/sessions/{session_id}/messages",
        headers=headers,
        json={"message": "Now help me travel.", "language": "en"},
    )
    read_after_block = client.get(f"/api/v1/search/ai/sessions/{session_id}", headers=headers)

    assert append_after_block.status_code == 409
    assert read_after_block.status_code == 200
    assert read_after_block.json()["status"] == "blocked"
