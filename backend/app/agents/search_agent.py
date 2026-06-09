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

from app.agents.ai_agent import AIClientError
from app.config import settings
from app.agents.context import ContextBuilder
from app.agents.memory import AgentMemoryService, get_agent_memory_service
from app.schemas import (
    AIChatMessage,
    AISearchResponse,
    AISearchSessionStatus,
    ParsedSearchRequest,
    SearchResponse,
)
from app.agents.search_agent_models import (
    AgentExtraction,
    AgentModelUsage,
    AgentScope,
    SearchAgentModel,
    get_search_agent_model,
    selected_agent_model_provider,
    validate_search_agent_model_config,
)
from app.agents.tools import AgentToolError, execute_agent_tool
from app.agents.token_usage import get_token_usage_recorder
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
    request_id: str
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
    context_stats: dict
    conversation_summary: str
    tool_results_summary: str
    search_history_summary: str
    memory_summary: str
    memory_updates: list[dict]
    cacheable_prefix_version: str
    context_overflow_count: int
    last_summary_turn: int


class SearchAgentService:
    def __init__(
        self,
        *,
        search_service: Optional[SearchService] = None,
        model: Optional[SearchAgentModel] = None,
        memory_service: Optional[AgentMemoryService] = None,
        checkpointer=None,
    ) -> None:
        self._search_service = search_service or get_search_service()
        self._model = model
        self._memory_service = memory_service or get_agent_memory_service()
        self._context_builder = ContextBuilder()
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
        request_id: Optional[str] = None,
    ) -> AISearchResponse:
        initial: AgentState = {
            "session_id": session_id,
            "user_id": user_id,
            "language": language,
            "user_message": message,
            "action": "message",
            "request_id": request_id or f"req_{uuid4().hex}",
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
            "context_stats": {},
            "conversation_summary": "",
            "tool_results_summary": "",
            "search_history_summary": "",
            "memory_summary": self._memory_service.build_summary(user_id, language=language),
            "memory_updates": [],
            "cacheable_prefix_version": "agent-context-v1",
            "context_overflow_count": 0,
            "last_summary_turn": 0,
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
        request_id: Optional[str] = None,
    ) -> AISearchResponse:
        with self._session_lock(session_id):
            self._raise_if_blocked(session_id)
            memory_summary = self._memory_summary_for_session(session_id, language)
            result = self._graph.invoke(
                {
                    "user_message": message,
                    "language": language,
                    "action": "message",
                    "stream_reply": stream_reply,
                    "request_id": request_id or f"req_{uuid4().hex}",
                    "memory_summary": memory_summary,
                },
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
        request_id: Optional[str] = None,
    ) -> AISearchResponse:
        with self._session_lock(session_id):
            self._raise_if_blocked(session_id)
            memory_summary = self._memory_summary_for_session(session_id, language)
            result = self._graph.invoke(
                {
                    "user_message": "",
                    "language": language,
                    "action": "confirm" if confirmed else "reject",
                    "stream_reply": stream_reply,
                    "request_id": request_id or f"req_{uuid4().hex}",
                    "memory_summary": memory_summary,
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

    def _memory_summary_for_session(self, session_id: str, language: str) -> str:
        snapshot = self._graph.get_state(self._thread_config(session_id))
        user_id = str((snapshot.values or {}).get("user_id") or "")
        return self._memory_service.build_summary(user_id, language=language) if user_id else ""

    def _record_usage(self, state: AgentState, call_type: str, usage: Optional[AgentModelUsage]) -> None:
        try:
            get_token_usage_recorder().record(
                user_id=str(state.get("user_id") or ""),
                session_id=str(state.get("session_id") or ""),
                request_id=str(state.get("request_id") or f"req_{uuid4().hex}"),
                call_type=call_type,
                usage=usage,
            )
        except Exception:
            return

    def _stream_usage_unavailable(self) -> AgentModelUsage:
        model = self._get_model()
        provider = str(getattr(model, "provider_name", selected_agent_model_provider()))
        model_name = settings.deepseek_model if provider == "deepseek" else settings.ai_model_name or provider
        return AgentModelUsage(provider=provider, model=model_name, usage_unavailable=True)

    @staticmethod
    def _is_context_length_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(term in message for term in ("context length", "context window", "maximum context", "token limit"))

    @staticmethod
    def _context_overflow_message(language: str) -> str:
        if language == "en":
            return (
                "This message or conversation is too long for the model context. "
                "Please split your travel need into a shorter message and send it again."
            )
        return "这段消息或当前会话内容过长，已经超过模型可安全处理的上下文。请把出行需求拆成更短的一段后再发送。"

    def _context_summary_updates(
        self,
        state: AgentState,
        *,
        conversation: Optional[list[AIChatMessage]] = None,
        parsed: Optional[ParsedSearchRequest] = None,
        tool_results: Optional[list[dict]] = None,
        search_history: Optional[list[dict]] = None,
        force_conversation_summary: bool = False,
    ) -> dict:
        updates: dict = {}
        parsed = parsed or ParsedSearchRequest.model_validate(state.get("parsed_request") or {})
        if conversation is not None and self._context_builder.should_refresh_conversation_summary(
            conversation,
            existing_summary=str(state.get("conversation_summary") or ""),
            force=force_conversation_summary,
        ):
            updates["conversation_summary"] = self._context_builder.summarize_conversation(conversation, parsed)
            updates["last_summary_turn"] = len(conversation)
        if tool_results is not None:
            updates["tool_results_summary"] = self._context_builder.summarize_tool_results(tool_results)
        if search_history is not None:
            updates["search_history_summary"] = self._context_builder.summarize_search_history(search_history)
        return updates

    def _memory_updates_for_turn(
        self,
        state: AgentState,
        *,
        parsed: ParsedSearchRequest,
        message: str = "",
        confirmed_search: bool = False,
    ) -> dict:
        user_id = str(state.get("user_id") or "")
        if not user_id:
            return {}
        memories = self._memory_service.update_from_turn(
            user_id=user_id,
            parsed_request=parsed,
            message=message,
            confirmed_search=confirmed_search,
        )
        language = str(state.get("language") or "zh")
        return {
            "memory_summary": self._memory_service.build_summary(user_id, language=language),
            "memory_updates": [item.model_dump(mode="json") for item in memories],
        }

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
            context = self._context_builder.build_for_extraction(
                message=message,
                parsed_request=parsed,
                conversation=conversation,
                conversation_summary=str(state.get("conversation_summary") or ""),
                tool_results_summary=str(state.get("tool_results_summary") or ""),
                search_history_summary=str(state.get("search_history_summary") or ""),
                memory_summary=str(state.get("memory_summary") or ""),
                force_compress=(
                    settings.ai_agent_compress_on_scope_violation
                    and state.get("scope") in {"off_topic_hard", "adversarial"}
                ),
            )
            try:
                extraction_result = self._get_model().extract(
                    message=context.latest_message,
                    language=state.get("language", "zh"),
                    parsed_request=parsed,
                    conversation=context.messages,
                    city_catalog=city_catalog,
                )
            except AIClientError as exc:
                if not self._is_context_length_error(exc) or context.compressed:
                    raise
                context = self._context_builder.build_for_extraction(
                    message=message,
                    parsed_request=parsed,
                    conversation=conversation,
                    conversation_summary=str(state.get("conversation_summary") or ""),
                    tool_results_summary=str(state.get("tool_results_summary") or ""),
                    search_history_summary=str(state.get("search_history_summary") or ""),
                    memory_summary=str(state.get("memory_summary") or ""),
                    force_compress=True,
                )
                try:
                    extraction_result = self._get_model().extract(
                        message=context.latest_message,
                        language=state.get("language", "zh"),
                        parsed_request=parsed,
                        conversation=context.messages,
                        city_catalog=city_catalog,
                    )
                except AIClientError as retry_exc:
                    if not self._is_context_length_error(retry_exc):
                        raise
                    conversation = [AIChatMessage.model_validate(item) for item in self._append_user_message(
                        [item.model_dump(mode="json") for item in conversation],
                        message,
                    )]
                    summary_updates = self._context_summary_updates(
                        state,
                        conversation=conversation,
                        parsed=parsed,
                        force_conversation_summary=True,
                    )
                    overflow_count = int(state.get("context_overflow_count") or 0) + 1
                    return {
                        "conversation": conversation,
                        "assistant_message": self._context_overflow_message(state.get("language", "zh")),
                        "intent": "context_overflow",
                        "tool_requests": [],
                        "tool_results": [],
                        "pending_reply": False,
                        "context_overflow_count": overflow_count,
                        "context_stats": {
                            "estimated_input_tokens": context.estimated_input_tokens,
                            "compressed": True,
                            "compression_reason": "context_length_retry_failed",
                        },
                        "status": AISearchSessionStatus.COLLECTING_REQUIRED.value,
                        **summary_updates,
                    }
            self._record_usage(state, "extract", extraction_result.usage)
            extraction = extraction_result.value
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
        summary_updates = self._context_summary_updates(
            state,
            conversation=conversation,
            parsed=parsed,
        )
        memory_updates = self._memory_updates_for_turn(
            state,
            parsed=parsed,
            message=message,
        )
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
            "context_stats": {
                "estimated_input_tokens": context.estimated_input_tokens if "context" in locals() else None,
                "compressed": context.compressed if "context" in locals() else False,
                "compression_reason": context.compression_reason if "context" in locals() else "",
            },
            "status": (
                AISearchSessionStatus.BLOCKED.value
                if blocked else
                AISearchSessionStatus.COLLECTING_REQUIRED.value
                if missing else AISearchSessionStatus.COLLECTING_OPTIONAL.value
            ),
            "search_response": None if action == "message" else state.get("search_response"),
            "search_executed": False if action == "message" else bool(state.get("search_executed")),
            "cacheable_prefix_version": context.cacheable_prefix_version if "context" in locals() else state.get("cacheable_prefix_version", "agent-context-v1"),
            **summary_updates,
            **memory_updates,
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
        return {
            "tool_results": results,
            "tool_requests": [],
            "tool_results_summary": self._context_builder.summarize_tool_results(results),
        }

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
        summary_updates = self._context_summary_updates(
            state,
            conversation=[AIChatMessage.model_validate(item) for item in conversation],
            parsed=parsed,
            search_history=history,
        )
        memory_updates = self._memory_updates_for_turn(
            state,
            parsed=parsed,
            confirmed_search=True,
        )
        return {
            "conversation": conversation,
            "assistant_message": message,
            "search_response": response.model_dump(mode="json"),
            "search_history": history,
            "search_executed": True,
            "status": AISearchSessionStatus.RESULTS_AVAILABLE.value,
            "summary": self._search_service._build_ai_summary(parsed, []),
            "pending_reply": False,
            **summary_updates,
            **memory_updates,
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
        elif state.get("intent") == "context_overflow":
            message = state.get("assistant_message", "") or self._context_overflow_message(language)
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
                conversation_for_reply = [
                    AIChatMessage.model_validate(item)
                    for item in state.get("conversation", [])
                ]
                reply_context = self._context_builder.build_for_reply(
                    parsed_request=parsed,
                    conversation=conversation_for_reply,
                    tool_results=state.get("tool_results") or [],
                    search_history=state.get("search_history") or [],
                    conversation_summary=str(state.get("conversation_summary") or ""),
                    tool_results_summary=str(state.get("tool_results_summary") or ""),
                    search_history_summary=str(state.get("search_history_summary") or ""),
                    memory_summary=str(state.get("memory_summary") or ""),
                )
                try:
                    reply_result = self._get_model().reply(
                        language=language,
                        parsed_request=parsed,
                        missing_fields=missing,
                        next_question_field=state.get("next_question_field"),
                        ready_for_confirmation=ready,
                        conversation=reply_context.messages,
                        tool_results=reply_context.tool_results,
                    )
                except AIClientError as exc:
                    if not self._is_context_length_error(exc):
                        raise
                    if reply_context.compressed:
                        message = self._context_overflow_message(language)
                        overflow_count = int(state.get("context_overflow_count") or 0) + 1
                    else:
                        reply_context = self._context_builder.build_for_reply(
                            parsed_request=parsed,
                            conversation=conversation_for_reply,
                            tool_results=state.get("tool_results") or [],
                            search_history=state.get("search_history") or [],
                            conversation_summary=str(state.get("conversation_summary") or ""),
                            tool_results_summary=str(state.get("tool_results_summary") or ""),
                            search_history_summary=str(state.get("search_history_summary") or ""),
                            memory_summary=str(state.get("memory_summary") or ""),
                            force_compress=True,
                        )
                        try:
                            reply_result = self._get_model().reply(
                                language=language,
                                parsed_request=parsed,
                                missing_fields=missing,
                                next_question_field=state.get("next_question_field"),
                                ready_for_confirmation=ready,
                                conversation=reply_context.messages,
                                tool_results=reply_context.tool_results,
                            )
                            self._record_usage(state, "reply", reply_result.usage)
                            message = reply_result.value
                            overflow_count = int(state.get("context_overflow_count") or 0)
                        except AIClientError as retry_exc:
                            if not self._is_context_length_error(retry_exc):
                                raise
                            message = self._context_overflow_message(language)
                            overflow_count = int(state.get("context_overflow_count") or 0) + 1
                else:
                    self._record_usage(state, "reply", reply_result.usage)
                    message = reply_result.value
                    overflow_count = int(state.get("context_overflow_count") or 0)
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
        summary_updates = self._context_summary_updates(
            state,
            conversation=[AIChatMessage.model_validate(item) for item in conversation],
            parsed=parsed,
            tool_results=state.get("tool_results") or [],
        )
        context_stats = dict(state.get("context_stats") or {})
        if "reply_context" in locals():
            context_stats = {
                **context_stats,
                "reply_estimated_input_tokens": reply_context.estimated_input_tokens,
                "reply_compressed": reply_context.compressed,
                "reply_compression_reason": reply_context.compression_reason,
                "cacheable_prefix_version": reply_context.cacheable_prefix_version,
                "dynamic_context_stats": reply_context.dynamic_context_stats,
            }
        return {
            "conversation": conversation,
            "assistant_message": message,
            "status": status,
            "summary": self._search_service._build_ai_summary(parsed, missing),
            "pending_reply": False,
            "context_overflow_count": overflow_count if "overflow_count" in locals() else int(state.get("context_overflow_count") or 0),
            "cacheable_prefix_version": reply_context.cacheable_prefix_version if "reply_context" in locals() else state.get("cacheable_prefix_version", "agent-context-v1"),
            "context_stats": context_stats,
            **summary_updates,
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
        snapshot = self._graph.get_state(self._thread_config(response.session_id))
        state = dict(snapshot.values or {})
        parsed = ParsedSearchRequest.model_validate(state.get("parsed_request") or response.parsed_request.model_dump(mode="json"))
        conversation = [
            AIChatMessage.model_validate(item)
            for item in state.get("conversation", [item.model_dump(mode="json") for item in response.conversation])
        ]
        reply_context = self._context_builder.build_for_reply(
            parsed_request=parsed,
            conversation=conversation,
            tool_results=state.get("tool_results") or [item.model_dump(mode="json") for item in response.tool_results],
            search_history=state.get("search_history") or [],
            conversation_summary=str(state.get("conversation_summary") or ""),
            tool_results_summary=str(state.get("tool_results_summary") or ""),
            search_history_summary=str(state.get("search_history_summary") or ""),
            memory_summary=str(state.get("memory_summary") or ""),
        )
        try:
            try:
                yield from self._get_model().stream_reply(
                    language=language,
                    parsed_request=parsed,
                    missing_fields=response.missing_fields,
                    next_question_field=response.next_question_field,
                    ready_for_confirmation=response.ready_for_confirmation,
                    conversation=reply_context.messages,
                    tool_results=reply_context.tool_results,
                )
            except AIClientError as exc:
                if not self._is_context_length_error(exc):
                    raise
                if reply_context.compressed:
                    yield self._context_overflow_message(language)
                else:
                    retry_context = self._context_builder.build_for_reply(
                        parsed_request=parsed,
                        conversation=conversation,
                        tool_results=state.get("tool_results") or [item.model_dump(mode="json") for item in response.tool_results],
                        search_history=state.get("search_history") or [],
                        conversation_summary=str(state.get("conversation_summary") or ""),
                        tool_results_summary=str(state.get("tool_results_summary") or ""),
                        search_history_summary=str(state.get("search_history_summary") or ""),
                        memory_summary=str(state.get("memory_summary") or ""),
                        force_compress=True,
                    )
                    try:
                        yield from self._get_model().stream_reply(
                            language=language,
                            parsed_request=parsed,
                            missing_fields=response.missing_fields,
                            next_question_field=response.next_question_field,
                            ready_for_confirmation=response.ready_for_confirmation,
                            conversation=retry_context.messages,
                            tool_results=retry_context.tool_results,
                        )
                    except AIClientError as retry_exc:
                        if not self._is_context_length_error(retry_exc):
                            raise
                        yield self._context_overflow_message(language)
        finally:
            latest = self._graph.get_state(self._thread_config(response.session_id))
            if latest.values:
                self._record_usage(latest.values, "stream_reply", self._stream_usage_unavailable())

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
            parsed = ParsedSearchRequest.model_validate(state.get("parsed_request") or {})
            summary_updates = self._context_summary_updates(
                state,
                conversation=[AIChatMessage.model_validate(item) for item in conversation],
                parsed=parsed,
                tool_results=state.get("tool_results") or [],
            )
            self._graph.update_state(
                self._thread_config(session_id),
                {
                    "conversation": conversation,
                    "assistant_message": message,
                    "pending_reply": False,
                    "stream_reply": False,
                    **summary_updates,
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
