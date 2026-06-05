from __future__ import annotations

import re
from functools import lru_cache
from threading import Lock
from typing import Optional, TypedDict
from uuid import uuid4

import psycopg
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row

from app.config import settings
from app.schemas import (
    AIChatMessage,
    AISearchResponse,
    AISearchSessionStatus,
    ParsedSearchRequest,
    SearchResponse,
)
from app.agents.search_agent_models import (
    AgentExtraction,
    SearchAgentModel,
    get_search_agent_model,
    selected_agent_model_provider,
    validate_search_agent_model_config,
)
from app.services.search_service import SearchService, get_search_service


OPTIONAL_FIELD_ORDER = [
    "optimization_target",
    "preferred_transport_types",
    "max_price",
    "max_transfers",
    "departure_time_range",
    "arrival_time_range",
    "allow_overnight",
    "required_transfer_cities",
    "excluded_cities",
    "max_total_duration_minutes",
]

CONFIRM_PATTERNS = (
    re.compile(r"^\s*(start|run|confirm)?\s*(search)\s*[.!?]?\s*$", re.I),
    re.compile(r"^\s*(search now|start search|confirm search|run search)\s*[.!?]?\s*$", re.I),
    re.compile(r"^\s*(搜索|确认搜索|开始搜索|执行搜索|现在搜索|就这样搜索)\s*[。.!?？]?\s*$"),
)
REJECT_PATTERNS = (
    re.compile(r"^\s*(not yet|do not search|cancel search)\s*[.!?]?\s*$", re.I),
    re.compile(r"^\s*(不要搜索|暂不搜索|先不搜索|取消搜索)\s*[。.!?？]?\s*$"),
)


class AgentState(TypedDict, total=False):
    session_id: str
    user_id: str
    language: str
    user_message: str
    action: str
    conversation: list[dict]
    parsed_request: dict
    answered_fields: list[str]
    skipped_fields: list[str]
    next_question_field: Optional[str]
    status: str
    assistant_message: str
    summary: str
    search_response: Optional[dict]
    search_history: list[dict]
    ready_for_confirmation: bool
    search_executed: bool
    intent: str


class SearchAgentService:
    def __init__(
        self,
        *,
        search_service: Optional[SearchService] = None,
        model: Optional[SearchAgentModel] = None,
        checkpointer=None,
    ) -> None:
        self._search_service = search_service or get_search_service()
        self._model = model
        if settings.ai_agent_turn_mode not in {"dual", "single"}:
            raise RuntimeError("AI_AGENT_TURN_MODE must be dual or single.")
        validate_search_agent_model_config()
        self._postgres_connection = None
        self._checkpointer = checkpointer or self._create_checkpointer()
        self._graph = self._build_graph()
        self._locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    def _create_checkpointer(self):
        if not settings.langgraph_checkpoint_database_url:
            if settings.app_env.lower() == "production":
                raise RuntimeError("LANGGRAPH_CHECKPOINT_DATABASE_URL is required in production.")
            return InMemorySaver()
        if not settings.langgraph_aes_key:
            raise RuntimeError("LANGGRAPH_AES_KEY is required when PostgreSQL checkpoints are enabled.")
        key = settings.langgraph_aes_key.encode("utf-8")
        if len(key) not in (16, 24, 32):
            raise RuntimeError("LANGGRAPH_AES_KEY must be 16, 24, or 32 bytes.")
        serde = EncryptedSerializer.from_pycryptodome_aes(key=key)
        self._postgres_connection = psycopg.connect(
            settings.langgraph_checkpoint_database_url,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
        )
        saver = PostgresSaver(self._postgres_connection, serde=serde)
        saver.setup()
        return saver

    def _build_graph(self):
        builder = StateGraph(AgentState)
        builder.add_node("understand", self._understand_node)
        builder.add_node("respond", self._respond_node)
        builder.add_node("search", self._search_node)
        builder.add_edge(START, "understand")
        builder.add_conditional_edges(
            "understand",
            self._route_after_understanding,
            {"search": "search", "respond": "respond"},
        )
        builder.add_edge("search", END)
        builder.add_edge("respond", END)
        return builder.compile(checkpointer=self._checkpointer)

    def _thread_config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    def _session_lock(self, session_id: str) -> Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, Lock())

    def create_session(self, *, session_id: str, user_id: str, message: str, language: str) -> AISearchResponse:
        initial: AgentState = {
            "session_id": session_id,
            "user_id": user_id,
            "language": language,
            "user_message": message,
            "action": "message",
            "conversation": [],
            "parsed_request": ParsedSearchRequest().model_dump(mode="json"),
            "answered_fields": [],
            "skipped_fields": [],
            "search_history": [],
            "search_executed": False,
        }
        with self._session_lock(session_id):
            result = self._graph.invoke(initial, self._thread_config(session_id), durability="sync")
        return self._to_response(result)

    def append_message(self, session_id: str, *, message: str, language: str) -> AISearchResponse:
        with self._session_lock(session_id):
            result = self._graph.invoke(
                {"user_message": message, "language": language, "action": "message"},
                self._thread_config(session_id),
                durability="sync",
            )
        return self._to_response(result)

    def confirm(self, session_id: str, *, confirmed: bool, language: str) -> AISearchResponse:
        with self._session_lock(session_id):
            result = self._graph.invoke(
                {"user_message": "", "language": language, "action": "confirm" if confirmed else "reject"},
                self._thread_config(session_id),
                durability="sync",
            )
        return self._to_response(result)

    def get_session(self, session_id: str) -> AISearchResponse:
        snapshot = self._graph.get_state(self._thread_config(session_id))
        if not snapshot.values:
            raise ValueError("AI session not found.")
        return self._to_response(snapshot.values)

    def delete_session(self, session_id: str) -> None:
        self._checkpointer.delete_thread(session_id)
        with self._locks_guard:
            self._locks.pop(session_id, None)

    def describe_backend(self) -> str:
        return (
            f"LangGraph/{type(self._checkpointer).__name__}/"
            f"{settings.ai_agent_turn_mode}/{selected_agent_model_provider()}"
        )

    def _get_model(self) -> SearchAgentModel:
        if self._model is None:
            self._model = get_search_agent_model()
        return self._model

    def _understand_node(self, state: AgentState) -> dict:
        parsed = ParsedSearchRequest.model_validate(state.get("parsed_request") or {})
        conversation = [AIChatMessage.model_validate(item) for item in state.get("conversation", [])]
        answered = set(state.get("answered_fields") or [])
        skipped = set(state.get("skipped_fields") or [])
        message = state.get("user_message", "").strip()
        action = state.get("action", "message")

        if action == "confirm":
            intent = "confirm_search"
            extraction = AgentExtraction(intent=intent)
        elif action == "reject":
            intent = "reject_search"
            extraction = AgentExtraction(intent=intent)
        elif any(pattern.match(message) for pattern in REJECT_PATTERNS):
            intent = "reject_search"
            extraction = AgentExtraction(intent=intent)
        elif any(pattern.match(message) for pattern in CONFIRM_PATTERNS):
            intent = "confirm_search"
            extraction = AgentExtraction(intent=intent)
        else:
            catalog = self._search_service._data_source.get_catalog()
            city_catalog = ", ".join(f"{city.name}({city.code}/{city.name_en})" for city in catalog.cities)
            extraction = self._get_model().extract(
                message=message,
                language=state.get("language", "zh"),
                parsed_request=parsed,
                conversation=conversation,
                city_catalog=city_catalog,
            )
            intent = extraction.intent

        if message:
            conversation.append(AIChatMessage(role="user", content=message))
        for field_name in extraction.cleared_fields:
            if field_name in ParsedSearchRequest.model_fields:
                setattr(parsed, field_name, [] if field_name in {"excluded_cities", "required_transfer_cities"} else None)
                answered.discard(field_name)
                skipped.discard(field_name)
        if extraction.parameter_patch:
            catalog = self._search_service._data_source.get_catalog()
            parsed = self._search_service._merge_parsed_request(parsed, extraction.parameter_patch, catalog.cities)
            answered.update(
                key for key, value in extraction.parameter_patch.items()
                if key in ParsedSearchRequest.model_fields and value is not None
            )
        skipped.update(field for field in extraction.skipped_fields if field in OPTIONAL_FIELD_ORDER)
        missing = self._search_service._missing_ai_fields(parsed)
        ready = not missing
        next_field = next(
            (field for field in OPTIONAL_FIELD_ORDER if field not in answered and field not in skipped),
            None,
        ) if ready else None
        return {
            "conversation": [item.model_dump(mode="json") for item in conversation],
            "parsed_request": parsed.model_dump(mode="json"),
            "answered_fields": sorted(answered),
            "skipped_fields": sorted(skipped),
            "next_question_field": next_field,
            "ready_for_confirmation": ready,
            "intent": intent,
            "assistant_message": extraction.assistant_message,
            "status": (
                AISearchSessionStatus.COLLECTING_REQUIRED.value
                if missing else AISearchSessionStatus.COLLECTING_OPTIONAL.value
            ),
            "search_response": None if action == "message" else state.get("search_response"),
            "search_executed": False if action == "message" else bool(state.get("search_executed")),
        }

    @staticmethod
    def _route_after_understanding(state: AgentState) -> str:
        return "search" if state.get("intent") == "confirm_search" and state.get("ready_for_confirmation") else "respond"

    def _search_node(self, state: AgentState) -> dict:
        parsed = ParsedSearchRequest.model_validate(state.get("parsed_request") or {})
        final_request = self._search_service._build_final_ai_request(parsed)
        if final_request is None:
            return self._respond_node(state)
        response = self._search_service.search(final_request)
        language = state.get("language", "zh")
        message = (
            "已按当前条件完成搜索。你可以继续补充或修改条件后再次搜索。"
            if language == "zh"
            else "Search complete. You can continue refining the conditions and search again."
        )
        conversation = list(state.get("conversation") or [])
        conversation.append(
            AIChatMessage(role="assistant", content=message, search_response=response).model_dump(mode="json")
        )
        history = list(state.get("search_history") or [])
        history.append(response.model_dump(mode="json"))
        return {
            "conversation": conversation,
            "assistant_message": message,
            "search_response": response.model_dump(mode="json"),
            "search_history": history,
            "search_executed": True,
            "status": AISearchSessionStatus.RESULTS_AVAILABLE.value,
            "summary": self._search_service._build_ai_summary(parsed, []),
        }

    def _respond_node(self, state: AgentState) -> dict:
        parsed = ParsedSearchRequest.model_validate(state.get("parsed_request") or {})
        missing = self._search_service._missing_ai_fields(parsed)
        ready = not missing
        language = state.get("language", "zh")
        if state.get("intent") == "reject_search":
            message = (
                "好的，我们继续调整条件。你可以告诉我想修改的内容。"
                if language == "zh"
                else "Okay, we can keep refining the conditions. Tell me what you want to change."
            )
        else:
            message = state.get("assistant_message", "").strip()
            if not message or settings.ai_agent_turn_mode == "dual":
                message = self._get_model().reply(
                    language=language,
                    parsed_request=parsed,
                    missing_fields=missing,
                    next_question_field=state.get("next_question_field"),
                    ready_for_confirmation=ready,
                    conversation=[AIChatMessage.model_validate(item) for item in state.get("conversation", [])],
                )
        conversation = list(state.get("conversation") or [])
        conversation.append(AIChatMessage(role="assistant", content=message).model_dump(mode="json"))
        status = (
            AISearchSessionStatus.COLLECTING_REQUIRED.value
            if missing
            else AISearchSessionStatus.AWAITING_CONFIRMATION.value
        )
        return {
            "conversation": conversation,
            "assistant_message": message,
            "status": status,
            "summary": self._search_service._build_ai_summary(parsed, missing),
        }

    def _to_response(self, state: AgentState) -> AISearchResponse:
        parsed = ParsedSearchRequest.model_validate(state.get("parsed_request") or {})
        final_request = self._search_service._build_final_ai_request(parsed)
        missing = self._search_service._missing_ai_fields(parsed)
        return AISearchResponse(
            session_id=state["session_id"],
            status=AISearchSessionStatus(state.get("status", AISearchSessionStatus.COLLECTING_REQUIRED.value)),
            assistant_message=state.get("assistant_message", ""),
            conversation=[AIChatMessage.model_validate(item) for item in state.get("conversation", [])],
            parsed_request=parsed,
            final_request=final_request,
            missing_fields=missing,
            summary=state.get("summary", ""),
            ready_for_confirmation=final_request is not None,
            search_executed=bool(state.get("search_executed")),
            search_response=(
                SearchResponse.model_validate(state["search_response"])
                if state.get("search_response") else None
            ),
            next_question_field=state.get("next_question_field"),
            answered_fields=state.get("answered_fields") or [],
            skipped_fields=state.get("skipped_fields") or [],
        )


@lru_cache
def get_search_agent_service() -> SearchAgentService:
    return SearchAgentService()


def reset_search_agent_service_cache() -> None:
    get_search_agent_service.cache_clear()


def new_ai_session_id() -> str:
    return f"ai_{uuid4().hex}"
