from __future__ import annotations

import re
from functools import lru_cache
from threading import Lock
from typing import Iterator, Optional, TypedDict
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
    AgentScope,
    SearchAgentModel,
    get_search_agent_model,
    selected_agent_model_provider,
    validate_search_agent_model_config,
)
from app.agents.tools import AgentToolError, execute_agent_tool
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
    re.compile("^\\s*(\\u641c\\u7d22|\\u5f00\\u59cb\\u641c\\u7d22|\\u786e\\u8ba4\\u641c\\u7d22|\\u6267\\u884c\\u641c\\u7d22|\\u73b0\\u5728\\u641c\\u7d22|\\u5c31\\u8fd9\\u6837\\u641c\\u7d22|\\u6309\\u8fd9\\u4e9b\\u6761\\u4ef6\\u641c\\u7d22)\\s*[\\u3002.!?\\uff1f]?\\s*$"),
)
REJECT_PATTERNS = (
    re.compile(r"^\s*(not yet|do not search|cancel search)\s*[.!?]?\s*$", re.I),
    re.compile("^\\s*(\\u4e0d\\u8981\\u641c\\u7d22|\\u6682\\u4e0d\\u641c\\u7d22|\\u5148\\u4e0d\\u641c\\u7d22|\\u53d6\\u6d88\\u641c\\u7d22|\\u7ee7\\u7eed\\u4fee\\u6539)\\s*[\\u3002.!?\\uff1f]?\\s*$"),
)

TRAVEL_SCOPES = {"route_search", "destination_discovery", "travel_context", "travel_tool_help"}
TOOL_ALLOWED_SCOPES = {"route_search", "destination_discovery", "travel_tool_help"}
DIRECT_RESPOND_SCOPES = {"destination_discovery", "travel_context", "off_topic_soft", "off_topic_hard", "adversarial"}

ADVERSARIAL_PATTERNS = (
    re.compile(r"(ignore|bypass|override|jailbreak).{0,40}(instruction|system|developer|policy|rule)", re.I),
    re.compile(r"(system prompt|developer message|hidden instruction)", re.I),
    re.compile(r"(忽略|绕过|覆盖|无视).{0,20}(指令|规则|限制|系统提示|开发者)", re.I),
    re.compile(r"(越狱|解除限制|泄露.*提示词|系统提示词)", re.I),
)
HARD_OFF_TOPIC_PATTERNS = (
    re.compile(r"\b(python|javascript|typescript|java|react|vue|sql|linux|docker|kubernetes)\b", re.I),
    re.compile(r"\b(code|coding|program|programming|debug|compiler|leetcode|algorithm)\b", re.I),
    re.compile(r"(写|生成|调试|解释).{0,12}(代码|程序|脚本|爬虫|正则|SQL|接口)", re.I),
    re.compile(r"(论文|作业|考试答案|商业文案|营销文案|角色扮演|扮演)", re.I),
)
TRAVEL_CONTEXT_PATTERNS = (
    re.compile(r"(小时候|童年|纪念|求婚|蜜月|毕业|家人|父母|朋友|故事|重要|仪式感|放松|散心|纪念日).{0,40}(旅行|旅游|出行|地方|城市|景点|路线|目的地)", re.I),
    re.compile(r"(旅行|旅游|出行|地方|城市|景点|路线|目的地).{0,40}(小时候|童年|纪念|求婚|蜜月|毕业|家人|父母|朋友|故事|重要|仪式感|放松|散心|纪念日)", re.I),
    re.compile(r"\b(childhood|meaningful|proposal|honeymoon|anniversary|graduation|family|memory|ceremonial|romantic)\b.{0,50}\b(trip|travel|destination|place|route)\b", re.I),
    re.compile(r"\b(trip|travel|destination|place|route)\b.{0,50}\b(childhood|meaningful|proposal|honeymoon|anniversary|graduation|family|memory|ceremonial|romantic)\b", re.I),
)
DESTINATION_DISCOVERY_PATTERNS = (
    re.compile(r"(想|打算|准备|计划).{0,12}(旅行|旅游|出去玩|出行).{0,30}(不知道|没想好|去哪|哪里|目的地|推荐)", re.I),
    re.compile(r"(推荐|找).{0,20}(目的地|旅行城市|旅游城市|旅行路线|旅游路线)", re.I),
    re.compile(r"\b(want|plan|planning|need).{0,20}(travel|trip|vacation).{0,50}(do not know|don't know|not sure|where to go|destination|recommend)\b", re.I),
    re.compile(r"\b(where should i go|recommend a destination|travel destination|trip ideas)\b", re.I),
)
SOFT_OFF_TOPIC_PATTERNS = (
    re.compile(r"^\s*(你好|您好|嗨|哈喽|hello|hi|hey|在吗|谢谢|thanks|thank you)\s*[。.!?？]*\s*$", re.I),
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
    tool_requests: list[dict]
    tool_results: list[dict]
    pending_reply: bool
    stream_reply: bool
    scope: str
    scope_confidence: float
    scope_reason: str
    off_topic_count: int
    hard_violation_count: int
    adversarial_count: int
    blocked_reason: str
    conversation_goal: str
    scope_guard_route: str


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
        builder.add_node("scope_guard", self._scope_guard_node)
        builder.add_node("understand", self._understand_node)
        builder.add_node("tool", self._tool_node)
        builder.add_node("respond", self._respond_node)
        builder.add_node("search", self._search_node)
        builder.add_node("blocked", self._blocked_node)
        builder.add_edge(START, "scope_guard")
        builder.add_conditional_edges(
            "scope_guard",
            self._route_after_scope_guard,
            {"understand": "understand", "respond": "respond", "blocked": "blocked"},
        )
        builder.add_conditional_edges(
            "understand",
            self._route_after_understanding,
            {"search": "search", "tool": "tool", "respond": "respond", "blocked": "blocked"},
        )
        builder.add_edge("tool", "respond")
        builder.add_edge("search", END)
        builder.add_edge("respond", END)
        builder.add_edge("blocked", END)
        return builder.compile(checkpointer=self._checkpointer)

    def _thread_config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    def _session_lock(self, session_id: str) -> Lock:
        with self._locks_guard:
            return self._locks.setdefault(session_id, Lock())

    def create_session(
        self,
        *,
        session_id: str,
        user_id: str,
        message: str,
        language: str,
        stream_reply: bool = False,
    ) -> AISearchResponse:
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
            "tool_results": [],
            "stream_reply": stream_reply,
            "scope": "route_search",
            "scope_confidence": 1.0,
            "scope_reason": "",
            "off_topic_count": 0,
            "hard_violation_count": 0,
            "adversarial_count": 0,
            "blocked_reason": "",
            "conversation_goal": "",
        }
        with self._session_lock(session_id):
            result = self._graph.invoke(initial, self._thread_config(session_id), durability="sync")
        return self._to_response(result)

    def append_message(
        self,
        session_id: str,
        *,
        message: str,
        language: str,
        stream_reply: bool = False,
    ) -> AISearchResponse:
        with self._session_lock(session_id):
            self._raise_if_blocked(session_id)
            result = self._graph.invoke(
                {"user_message": message, "language": language, "action": "message", "stream_reply": stream_reply},
                self._thread_config(session_id),
                durability="sync",
            )
        return self._to_response(result)

    def confirm(
        self,
        session_id: str,
        *,
        confirmed: bool,
        language: str,
        stream_reply: bool = False,
    ) -> AISearchResponse:
        with self._session_lock(session_id):
            self._raise_if_blocked(session_id)
            result = self._graph.invoke(
                {
                    "user_message": "",
                    "language": language,
                    "action": "confirm" if confirmed else "reject",
                    "stream_reply": stream_reply,
                },
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

    def _raise_if_blocked(self, session_id: str) -> None:
        snapshot = self._graph.get_state(self._thread_config(session_id))
        if snapshot.values and snapshot.values.get("status") == AISearchSessionStatus.BLOCKED.value:
            raise ValueError("AI session is blocked.")

    @staticmethod
    def _append_user_message(conversation: list[dict], message: str) -> list[dict]:
        if not message:
            return conversation
        if conversation and conversation[-1].get("role") == "user" and conversation[-1].get("content") == message:
            return conversation
        return [*conversation, AIChatMessage(role="user", content=message).model_dump(mode="json")]

    @staticmethod
    def _rule_scope(message: str) -> tuple[Optional[AgentScope], float, str]:
        if not message.strip():
            return None, 0.0, ""
        for pattern in ADVERSARIAL_PATTERNS:
            if pattern.search(message):
                return "adversarial", 0.98, "adversarial_instruction_attempt"
        for pattern in HARD_OFF_TOPIC_PATTERNS:
            if pattern.search(message):
                return "off_topic_hard", 0.94, "non_travel_task"
        for pattern in TRAVEL_CONTEXT_PATTERNS:
            if pattern.search(message):
                return "travel_context", 0.86, "travel_relevant_personal_context"
        for pattern in DESTINATION_DISCOVERY_PATTERNS:
            if pattern.search(message):
                return "destination_discovery", 0.88, "destination_discovery_request"
        for pattern in SOFT_OFF_TOPIC_PATTERNS:
            if pattern.search(message):
                return "off_topic_soft", 0.80, "small_talk"
        return None, 0.0, ""

    def _counts_after_scope(self, state: AgentState, scope: str) -> tuple[int, int, int]:
        off_topic_count = int(state.get("off_topic_count") or 0)
        hard_count = int(state.get("hard_violation_count") or 0)
        adversarial_count = int(state.get("adversarial_count") or 0)
        if scope in {"off_topic_hard", "adversarial"}:
            off_topic_count += 1
        if scope == "off_topic_hard":
            hard_count += 1
        if scope == "adversarial":
            adversarial_count += 1
        if scope in TRAVEL_SCOPES:
            off_topic_count = 0
            hard_count = 0
            adversarial_count = 0
        return off_topic_count, hard_count, adversarial_count

    def _is_block_threshold_reached(self, hard_count: int, adversarial_count: int) -> bool:
        return (
            hard_count >= settings.ai_agent_hard_off_topic_limit
            or adversarial_count >= settings.ai_agent_adversarial_limit
        )

    def _scope_guard_node(self, state: AgentState) -> dict:
        if not settings.ai_agent_scope_guard_enabled or state.get("action") != "message":
            return {"scope": state.get("scope", "route_search"), "scope_guard_route": "understand"}
        if state.get("status") == AISearchSessionStatus.BLOCKED.value:
            return {"scope_guard_route": "blocked"}
        message = state.get("user_message", "").strip()
        scope, confidence, reason = self._rule_scope(message)
        if scope is None:
            return {"scope": "route_search", "scope_confidence": 0.5, "scope_reason": "", "scope_guard_route": "understand"}

        off_count, hard_count, adversarial_count = self._counts_after_scope(state, scope)
        blocked = self._is_block_threshold_reached(hard_count, adversarial_count)
        conversation = self._append_user_message(list(state.get("conversation") or []), message)
        return {
            "conversation": conversation,
            "scope": scope,
            "scope_confidence": confidence,
            "scope_reason": reason,
            "off_topic_count": off_count,
            "hard_violation_count": hard_count,
            "adversarial_count": adversarial_count,
            "blocked_reason": reason if blocked else "",
            "tool_requests": [],
            "tool_results": [],
            "pending_reply": False,
            "scope_guard_route": "blocked" if blocked else "respond",
            "status": AISearchSessionStatus.BLOCKED.value if blocked else state.get("status", AISearchSessionStatus.COLLECTING_REQUIRED.value),
        }

    @staticmethod
    def _route_after_scope_guard(state: AgentState) -> str:
        return str(state.get("scope_guard_route") or "understand")

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
        scope = extraction.scope
        scope_confidence = extraction.scope_confidence
        if scope_confidence < settings.ai_agent_scope_confidence_threshold:
            scope = "route_search"
        off_count, hard_count, adversarial_count = self._counts_after_scope(state, scope)
        blocked = self._is_block_threshold_reached(hard_count, adversarial_count)

        if message:
            conversation = [AIChatMessage.model_validate(item) for item in self._append_user_message(
                [item.model_dump(mode="json") for item in conversation],
                message,
            )]
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
            "conversation": conversation,
            "parsed_request": parsed.model_dump(mode="json"),
            "answered_fields": sorted(answered),
            "skipped_fields": sorted(skipped),
            "next_question_field": next_field,
            "ready_for_confirmation": ready,
            "intent": intent,
            "assistant_message": extraction.assistant_message,
            "tool_requests": [
                item.model_dump(mode="json")
                for item in extraction.tool_requests[:2]
            ] if scope in TOOL_ALLOWED_SCOPES else [],
            "tool_results": [],
            "pending_reply": False,
            "scope": scope,
            "scope_confidence": scope_confidence,
            "scope_reason": extraction.scope_reason,
            "off_topic_count": off_count,
            "hard_violation_count": hard_count,
            "adversarial_count": adversarial_count,
            "blocked_reason": extraction.refusal_reason or extraction.scope_reason if blocked else "",
            "conversation_goal": extraction.conversation_goal,
            "status": (
                AISearchSessionStatus.BLOCKED.value
                if blocked else
                AISearchSessionStatus.COLLECTING_REQUIRED.value
                if missing else AISearchSessionStatus.COLLECTING_OPTIONAL.value
            ),
            "search_response": None if action == "message" else state.get("search_response"),
            "search_executed": False if action == "message" else bool(state.get("search_executed")),
        }

    @staticmethod
    def _route_after_understanding(state: AgentState) -> str:
        if state.get("status") == AISearchSessionStatus.BLOCKED.value:
            return "blocked"
        if state.get("scope") in DIRECT_RESPOND_SCOPES:
            return "respond"
        if state.get("intent") == "confirm_search" and state.get("ready_for_confirmation"):
            return "search"
        if state.get("tool_requests"):
            return "tool"
        return "respond"

    def _tool_node(self, state: AgentState) -> dict:
        results = []
        for request in state.get("tool_requests") or []:
            name = str(request.get("name") or "")
            arguments = request.get("arguments") if isinstance(request.get("arguments"), dict) else {}
            try:
                result = execute_agent_tool(name, arguments)
                results.append({
                    "name": result.name,
                    "status": result.status,
                    "content": result.content,
                    "data": result.data,
                })
            except AgentToolError as exc:
                results.append({
                    "name": name or "unknown",
                    "status": "error",
                    "content": str(exc),
                    "data": {},
                })
        return {"tool_results": results, "tool_requests": []}

    def _search_node(self, state: AgentState) -> dict:
        parsed = ParsedSearchRequest.model_validate(state.get("parsed_request") or {})
        final_request = self._search_service._build_final_ai_request(parsed)
        if final_request is None:
            return self._respond_node(state)
        response = self._search_service.search(final_request)
        language = state.get("language", "zh")
        message = (
            "\u5df2\u6309\u5f53\u524d\u6761\u4ef6\u5b8c\u6210\u641c\u7d22\u3002\u4f60\u53ef\u4ee5\u7ee7\u7eed\u8865\u5145\u6216\u4fee\u6539\u6761\u4ef6\u540e\u518d\u6b21\u641c\u7d22\u3002"
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
            "pending_reply": False,
        }

    def _respond_node(self, state: AgentState) -> dict:
        parsed = ParsedSearchRequest.model_validate(state.get("parsed_request") or {})
        missing = self._search_service._missing_ai_fields(parsed)
        ready = not missing
        language = state.get("language", "zh")
        scope = state.get("scope", "route_search")
        if state.get("status") == AISearchSessionStatus.BLOCKED.value:
            return self._blocked_node(state)
        if scope in {"off_topic_hard", "adversarial", "off_topic_soft", "destination_discovery", "travel_context"}:
            message = self._scope_response(scope, language)
        elif state.get("intent") == "reject_search":
            message = (
                "\u597d\u7684\uff0c\u6211\u4eec\u7ee7\u7eed\u8c03\u6574\u6761\u4ef6\u3002\u4f60\u53ef\u4ee5\u544a\u8bc9\u6211\u60f3\u4fee\u6539\u7684\u5185\u5bb9\u3002"
                if language == "zh"
                else "Okay, we can keep refining the conditions. Tell me what you want to change."
            )
        else:
            message = state.get("assistant_message", "").strip()
            if state.get("stream_reply"):
                return {
                    "assistant_message": "",
                    "pending_reply": True,
                    "status": (
                        AISearchSessionStatus.COLLECTING_REQUIRED.value
                        if missing
                        else AISearchSessionStatus.AWAITING_CONFIRMATION.value
                    ),
                    "summary": self._search_service._build_ai_summary(parsed, missing),
                }
            if not message or settings.ai_agent_turn_mode == "dual":
                message = self._get_model().reply(
                    language=language,
                    parsed_request=parsed,
                    missing_fields=missing,
                    next_question_field=state.get("next_question_field"),
                    ready_for_confirmation=ready,
                    conversation=[AIChatMessage.model_validate(item) for item in state.get("conversation", [])],
                    tool_results=state.get("tool_results") or [],
                )
        conversation = list(state.get("conversation") or [])
        conversation.append(
            AIChatMessage(
                role="assistant",
                content=message,
                tool_results=state.get("tool_results") or [],
            ).model_dump(mode="json")
        )
        status = (
            AISearchSessionStatus.BLOCKED.value
            if state.get("status") == AISearchSessionStatus.BLOCKED.value else
            AISearchSessionStatus.COLLECTING_REQUIRED.value
            if missing
            else AISearchSessionStatus.AWAITING_CONFIRMATION.value
        )
        return {
            "conversation": conversation,
            "assistant_message": message,
            "status": status,
            "summary": self._search_service._build_ai_summary(parsed, missing),
            "pending_reply": False,
        }

    @staticmethod
    def _scope_response(scope: str, language: str) -> str:
        if language == "en":
            messages = {
                "off_topic_hard": "I can’t help with that non-travel task here. I can help plan routes, destinations, weather, and verified places. Which city will you depart from?",
                "adversarial": "This assistant is limited to travel planning. I can help with routes, destinations, weather, and verified places.",
                "off_topic_soft": "Hi. I can help plan routes, destinations, weather, and verified places. What trip are you considering?",
                "destination_discovery": "We can start without a fixed destination. Which city will you depart from, and what kind of trip do you want: relaxing, scenic, family, romantic, or budget-friendly?",
                "travel_context": "That sounds meaningful. For this trip, should the route feel more commemorative, quiet and restorative, or ceremonial?",
            }
            return messages.get(scope, messages["off_topic_soft"])
        messages = {
            "off_topic_hard": "我不能在这里完成这个非旅行任务。这个助手可以帮你规划路线、目的地、天气和真实地点建议。你想从哪个城市出发？",
            "adversarial": "这个助手仅支持旅行规划相关内容。我可以帮你规划路线、目的地、天气和真实地点建议。",
            "off_topic_soft": "你好，我可以帮你规划路线、目的地、天气和真实地点建议。你正在考虑一次什么样的出行？",
            "destination_discovery": "可以先不确定目的地。你从哪个城市出发？这次旅行更偏放松、风景、亲子、浪漫，还是低预算？",
            "travel_context": "这件事听起来对你很重要。你希望这次旅行更偏纪念感、安静陪伴，还是有明确仪式感？",
        }
        return messages.get(scope, messages["off_topic_soft"])

    def _blocked_node(self, state: AgentState) -> dict:
        language = state.get("language", "zh")
        message = (
            "This conversation has been paused because it repeatedly moved away from travel planning. You can start a new conversation for travel planning."
            if language == "en"
            else "当前会话因多次偏离旅行用途已暂停。你可以新建会话继续旅行规划。"
        )
        conversation = list(state.get("conversation") or [])
        if not conversation or conversation[-1].get("role") != "assistant" or conversation[-1].get("content") != message:
            conversation.append(AIChatMessage(role="assistant", content=message).model_dump(mode="json"))
        return {
            "conversation": conversation,
            "assistant_message": message,
            "status": AISearchSessionStatus.BLOCKED.value,
            "tool_requests": [],
            "tool_results": [],
            "pending_reply": False,
            "search_executed": False,
        }

    def stream_reply_chunks(self, response: AISearchResponse, *, language: str = "zh") -> Iterator[str]:
        yield from self._get_model().stream_reply(
            language=language,
            parsed_request=response.parsed_request,
            missing_fields=response.missing_fields,
            next_question_field=response.next_question_field,
            ready_for_confirmation=response.ready_for_confirmation,
            conversation=response.conversation,
            tool_results=[item.model_dump(mode="json") for item in response.tool_results],
        )

    def complete_streaming_reply(self, session_id: str, message: str) -> AISearchResponse:
        with self._session_lock(session_id):
            snapshot = self._graph.get_state(self._thread_config(session_id))
            if not snapshot.values:
                raise ValueError("AI session not found.")
            state = dict(snapshot.values)
            conversation = list(state.get("conversation") or [])
            conversation.append(
                AIChatMessage(
                    role="assistant",
                    content=message or " ",
                    tool_results=state.get("tool_results") or [],
                ).model_dump(mode="json")
            )
            self._graph.update_state(
                self._thread_config(session_id),
                {
                    "conversation": conversation,
                    "assistant_message": message,
                    "pending_reply": False,
                    "stream_reply": False,
                },
            )
        return self.get_session(session_id)

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
            tool_results=state.get("tool_results") or [],
            pending_reply=bool(state.get("pending_reply")),
        )


@lru_cache
def get_search_agent_service() -> SearchAgentService:
    return SearchAgentService()


def reset_search_agent_service_cache() -> None:
    get_search_agent_service.cache_clear()


def new_ai_session_id() -> str:
    return f"ai_{uuid4().hex}"
