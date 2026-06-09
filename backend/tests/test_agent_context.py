from app.agents.context import ContextBuilder
from app.agents.ai_agent import AIClientError
from app.agents.search_agent import SearchAgentService
from app.agents.search_agent_models import AgentExtraction, AgentModelResult
from app.config import settings
from app.schemas import AIChatMessage, ParsedSearchRequest


class _RetryModel:
    provider_name = "test"

    def __init__(self, *, fail_calls: set[int]) -> None:
        self.fail_calls = fail_calls
        self.extract_call_count = 0
        self.extract_context_lengths: list[int] = []

    def extract(self, *, message, language, parsed_request, conversation, city_catalog):
        del message, language, parsed_request, city_catalog
        self.extract_call_count += 1
        self.extract_context_lengths.append(len(conversation))
        if self.extract_call_count in self.fail_calls:
            raise AIClientError("maximum context length exceeded")
        return AgentModelResult(
            value=AgentExtraction(intent="continue", assistant_message="model ok")
        )

    def reply(self, *, language, parsed_request, missing_fields, next_question_field, ready_for_confirmation, conversation, tool_results=None):
        del language, parsed_request, missing_fields, next_question_field, ready_for_confirmation, conversation, tool_results
        return AgentModelResult(value="reply ok")

    def stream_reply(self, *, language, parsed_request, missing_fields, next_question_field, ready_for_confirmation, conversation, tool_results=None):
        del language, parsed_request, missing_fields, next_question_field, ready_for_confirmation, conversation, tool_results
        yield "reply ok"


def test_context_builder_keeps_full_normal_travel_history(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_search_max_history_messages", 3)
    monkeypatch.setattr(settings, "ai_agent_context_hard_input_token_limit", 0)
    conversation = [
        AIChatMessage(role="user", content=f"travel preference {index}")
        for index in range(10)
    ]

    result = ContextBuilder().build_for_extraction(
        message="I want to go from Beijing to Shanghai tomorrow.",
        parsed_request=ParsedSearchRequest(),
        conversation=conversation,
    )

    assert result.compressed is False
    assert len(result.messages) == 10


def test_context_builder_injects_long_term_memory_without_compression() -> None:
    result = ContextBuilder().build_for_extraction(
        message="I want to travel tomorrow.",
        parsed_request=ParsedSearchRequest(),
        conversation=[AIChatMessage(role="user", content="Previous turn")],
        memory_summary="User often departs from Beijing and prefers train.",
    )

    assert result.compressed is False
    assert len(result.messages) == 2
    assert "Long-term memory summary" in result.messages[0].content
    assert "prefers train" in result.messages[0].content
    assert result.cacheable_prefix_version == "agent-context-v1"


def test_context_builder_compresses_when_forced_by_scope_violation(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_search_max_history_messages", 3)
    monkeypatch.setattr(settings, "ai_agent_context_recent_turns_after_summary", 3)
    conversation = [
        AIChatMessage(role="user", content=f"message {index}")
        for index in range(10)
    ]

    result = ContextBuilder().build_for_extraction(
        message="write code " * 1000,
        parsed_request=ParsedSearchRequest(),
        conversation=conversation,
        force_compress=True,
    )

    assert result.compressed is True
    assert result.compression_reason == "scope_violation"
    assert len(result.messages) == 3


def test_context_builder_creates_conversation_summary_after_trigger(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_agent_context_summary_trigger_messages", 4)
    conversation = [
        AIChatMessage(role="user", content=f"I prefer quiet travel {index}")
        for index in range(4)
    ]
    builder = ContextBuilder()

    assert builder.should_refresh_conversation_summary(conversation) is True
    summary = builder.summarize_conversation(
        conversation,
        ParsedSearchRequest(from_city="Beijing", to_city="Shanghai"),
    )

    assert "current_parameters" in summary
    assert "quiet travel" in summary


def test_context_builder_injects_summaries_when_compressed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_agent_context_recent_turns_after_summary", 2)
    conversation = [
        AIChatMessage(role="user", content=f"message {index}")
        for index in range(6)
    ]

    result = ContextBuilder().build_for_extraction(
        message="Beijing to Shanghai tomorrow",
        parsed_request=ParsedSearchRequest(),
        conversation=conversation,
        conversation_summary="User wants a quiet anniversary trip.",
        tool_results_summary="Weather is rainy.",
        search_history_summary="Previous route was Beijing -> Nanjing -> Shanghai.",
        force_compress=True,
    )

    assert result.compressed is True
    assert len(result.messages) == 3
    assert "Conversation summary" in result.messages[0].content
    assert "Weather is rainy" in result.messages[0].content


def test_context_builder_summarizes_large_tool_results_for_reply(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_agent_context_max_tool_result_chars", 200)
    tool_results = [{
        "name": "place_search",
        "status": "success",
        "content": "x" * 500,
        "data": {
            "verified_pois": [
                {
                    "name": "West Lake",
                    "city": "Hangzhou",
                    "address": "Xihu District",
                    "verification_status": "single_verified",
                    "provider": "amap",
                    "raw": "y" * 1000,
                }
            ]
        },
    }]

    result = ContextBuilder().build_for_reply(
        parsed_request=ParsedSearchRequest(),
        conversation=[AIChatMessage(role="user", content="Find a romantic place.")],
        tool_results=tool_results,
    )

    assert result.compressed is True
    assert result.tool_results[0]["name"] == "context_summary"
    assert "West Lake" in result.tool_results[0]["data"]["summary"]
    assert "raw" not in result.tool_results[0]["data"]["summary"]


def test_search_agent_retries_context_length_error_with_compressed_context(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_model_provider", "legacy")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "ai_agent_context_recent_turns_after_summary", 1)
    model = _RetryModel(fail_calls={2})
    service = SearchAgentService(model=model)

    response = service.create_session(
        session_id="ctx_retry_session",
        user_id="user-1",
        message="I want to travel.",
        language="en",
    )
    response = service.append_message(
        response.session_id,
        message="Beijing to Shanghai tomorrow.",
        language="en",
    )

    assert response.assistant_message == "reply ok"
    assert model.extract_call_count == 3
    assert model.extract_context_lengths[2] < model.extract_context_lengths[1]


def test_search_agent_returns_friendly_message_when_context_retry_still_fails(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_model_provider", "legacy")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    model = _RetryModel(fail_calls={2, 3})
    service = SearchAgentService(model=model)

    response = service.create_session(
        session_id="ctx_retry_failed_session",
        user_id="user-1",
        message="I want to travel.",
        language="en",
    )
    response = service.append_message(
        response.session_id,
        message="Beijing to Shanghai tomorrow.",
        language="en",
    )

    assert "too long" in response.assistant_message
    assert response.status.value == "collecting_required"
