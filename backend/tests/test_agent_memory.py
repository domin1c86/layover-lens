from app.agents.memory import AgentMemoryService
from app.agents.search_agent import SearchAgentService
from app.agents.search_agent_models import AgentExtraction, AgentModelResult
from app.config import settings
from app.schemas import ParsedSearchRequest


class _CaptureModel:
    provider_name = "test"

    def __init__(self) -> None:
        self.extract_conversations = []

    def extract(self, *, message, language, parsed_request, conversation, city_catalog):
        del message, language, parsed_request, city_catalog
        self.extract_conversations.append(conversation)
        return AgentModelResult(value=AgentExtraction(intent="continue", assistant_message="ok"))

    def reply(self, *, language, parsed_request, missing_fields, next_question_field, ready_for_confirmation, conversation, tool_results=None):
        del language, parsed_request, missing_fields, next_question_field, ready_for_confirmation, conversation, tool_results
        return AgentModelResult(value="reply ok")

    def stream_reply(self, *, language, parsed_request, missing_fields, next_question_field, ready_for_confirmation, conversation, tool_results=None):
        del language, parsed_request, missing_fields, next_question_field, ready_for_confirmation, conversation, tool_results
        yield "reply ok"


def test_agent_memory_learns_departure_city_and_travel_style(monkeypatch) -> None:
    monkeypatch.setattr(settings, "database_url", "mysql://invalid:invalid@127.0.0.1:1/missing")
    monkeypatch.setattr(settings, "ai_agent_long_term_memory_enabled", True)
    service = AgentMemoryService()

    updated = service.update_from_turn(
        user_id="user-memory-1",
        parsed_request=ParsedSearchRequest(
            from_city="Beijing",
            to_city="Hangzhou",
            preferred_transport_types=["train"],
        ),
        message="I want a quiet and romantic trip.",
    )
    memories = service.list_memories("user-memory-1")
    summary = service.build_summary("user-memory-1")

    keys = {item.memory_key for item in memories}
    assert updated
    assert "frequent_departure_city" in keys
    assert "preferred_transport_type:train" in keys
    assert "travel_style:romantic" in keys
    assert "travel_style:quiet" in keys
    assert "Beijing" in summary


def test_agent_memory_delete_and_clear(monkeypatch) -> None:
    monkeypatch.setattr(settings, "database_url", "mysql://invalid:invalid@127.0.0.1:1/missing")
    service = AgentMemoryService()
    service.update_from_turn(
        user_id="user-memory-2",
        parsed_request=ParsedSearchRequest(from_city="Shanghai", to_city="Chengdu"),
    )

    assert service.delete_memory("user-memory-2", "frequent_departure_city") is True
    assert "frequent_departure_city" not in {item.memory_key for item in service.list_memories("user-memory-2")}

    service.clear_memories("user-memory-2")
    assert service.list_memories("user-memory-2") == []


def test_search_agent_injects_cross_session_memory(monkeypatch) -> None:
    monkeypatch.setattr(settings, "database_url", "mysql://invalid:invalid@127.0.0.1:1/missing")
    monkeypatch.setattr(settings, "ai_model_provider", "legacy")
    memory_service = AgentMemoryService()
    memory_service.update_from_turn(
        user_id="user-memory-3",
        parsed_request=ParsedSearchRequest(from_city="Beijing", preferred_transport_types=["train"]),
    )
    model = _CaptureModel()
    service = SearchAgentService(model=model, memory_service=memory_service)

    service.create_session(
        session_id="memory_injection_session",
        user_id="user-memory-3",
        message="I want to travel tomorrow.",
        language="en",
    )

    assert model.extract_conversations
    first_context = model.extract_conversations[0]
    assert "Long-term memory summary" in first_context[0].content
    assert "Beijing" in first_context[0].content
