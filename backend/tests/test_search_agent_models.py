import json

import pytest

from app.config import settings
from app.schemas import ParsedSearchRequest
from app.agents.ai_agent import AIClientError
from app.agents.search_agent_models import (
    LegacyCompatibleAgentModel,
    OpenAICompatibleHttpAgentModel,
    get_search_agent_model,
    selected_agent_model_provider,
    validate_search_agent_model_config,
)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeStreamResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self):
        yield from self._lines


def _set_openai_compatible(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_model_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_model_api_key", "test-key")
    monkeypatch.setattr(settings, "ai_model_base_url", "https://mimo.example/v1")
    monkeypatch.setattr(settings, "ai_model_name", "mimo-test")
    monkeypatch.setattr(settings, "ai_model_timeout_seconds", 12.0)
    monkeypatch.setattr(settings, "ai_model_supports_json_mode", True)


def test_deepseek_provider_without_key_uses_legacy_in_development(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "ai_model_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "")

    assert selected_agent_model_provider() == "legacy"
    assert isinstance(get_search_agent_model(), LegacyCompatibleAgentModel)


def test_openai_compatible_extract_sends_chat_completion_request(monkeypatch) -> None:
    _set_openai_compatible(monkeypatch)
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        content = {
            "parameter_patch": {
                "from_city": "Beijing",
                "to_city": "Shanghai",
                "travel_date": "2026-06-05",
            },
            "intent": "provide_parameters",
            "assistant_message": "Please confirm the search.",
        }
        return _FakeResponse({"choices": [{"message": {"content": json_dumps(content)}}]})

    monkeypatch.setattr("app.agents.search_agent_models.httpx.post", fake_post)

    extraction = OpenAICompatibleHttpAgentModel().extract(
        message="Beijing to Shanghai on 2026-06-05",
        language="en",
        parsed_request=ParsedSearchRequest(),
        conversation=[],
        city_catalog="Beijing(BJ/Beijing), Shanghai(SH/Shanghai)",
    )

    assert captured["url"] == "https://mimo.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "mimo-test"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert captured["timeout"] == 12.0
    assert extraction.parameter_patch["from_city"] == "Beijing"
    assert extraction.parameter_patch["travel_date"] == "2026-06-05"


def test_openai_compatible_reply_does_not_force_json_mode(monkeypatch) -> None:
    _set_openai_compatible(monkeypatch)
    captured = {}

    def fake_post(url, *, headers, json, timeout):
        del url, headers, timeout
        captured["json"] = json
        return _FakeResponse({"choices": [{"message": {"content": "What date do you want to travel?"}}]})

    monkeypatch.setattr("app.agents.search_agent_models.httpx.post", fake_post)

    message = OpenAICompatibleHttpAgentModel().reply(
        language="en",
        parsed_request=ParsedSearchRequest(from_city="Beijing", to_city="Shanghai"),
        missing_fields=["travel_date"],
        next_question_field=None,
        ready_for_confirmation=False,
        conversation=[],
    )

    assert "response_format" not in captured["json"]
    assert message == "What date do you want to travel?"


def test_openai_compatible_stream_reply_reads_sse_deltas(monkeypatch) -> None:
    _set_openai_compatible(monkeypatch)
    captured = {}

    def fake_stream(method, url, *, headers, json, timeout):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _FakeStreamResponse([
            'data: {"choices":[{"delta":{"content":"What "}}]}',
            'data: {"choices":[{"delta":{"content":"date?"}}]}',
            "data: [DONE]",
        ])

    monkeypatch.setattr("app.agents.search_agent_models.httpx.stream", fake_stream)

    chunks = list(OpenAICompatibleHttpAgentModel().stream_reply(
        language="en",
        parsed_request=ParsedSearchRequest(from_city="Beijing", to_city="Shanghai"),
        missing_fields=["travel_date"],
        next_question_field=None,
        ready_for_confirmation=False,
        conversation=[],
    ))

    assert captured["method"] == "POST"
    assert captured["url"] == "https://mimo.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["stream"] is True
    assert captured["timeout"] == 12.0
    assert chunks == ["What ", "date?"]


def test_openai_compatible_extract_rejects_invalid_json(monkeypatch) -> None:
    _set_openai_compatible(monkeypatch)

    def fake_post(url, *, headers, json, timeout):
        del url, headers, json, timeout
        return _FakeResponse({"choices": [{"message": {"content": "not json"}}]})

    monkeypatch.setattr("app.agents.search_agent_models.httpx.post", fake_post)

    with pytest.raises(AIClientError):
        OpenAICompatibleHttpAgentModel().extract(
            message="Beijing to Shanghai",
            language="en",
            parsed_request=ParsedSearchRequest(),
            conversation=[],
            city_catalog="Beijing(BJ/Beijing), Shanghai(SH/Shanghai)",
        )


def test_openai_compatible_requires_complete_config(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_model_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_model_api_key", "")
    monkeypatch.setattr(settings, "ai_model_base_url", "https://mimo.example/v1")
    monkeypatch.setattr(settings, "ai_model_name", "mimo-test")

    with pytest.raises(RuntimeError, match="AI_MODEL_API_KEY"):
        validate_search_agent_model_config()


def test_legacy_provider_is_not_allowed_in_production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "ai_model_provider", "legacy")

    with pytest.raises(RuntimeError, match="legacy"):
        validate_search_agent_model_config()


def json_dumps(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False)
