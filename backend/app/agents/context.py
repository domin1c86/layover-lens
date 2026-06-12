from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable, Optional

from app.config import settings
from app.schemas import AIChatMessage, ParsedSearchRequest


@dataclass(frozen=True)
class ContextBuildResult:
    messages: list[AIChatMessage]
    latest_message: str
    estimated_input_tokens: int
    compressed: bool = False
    compression_reason: str = ""
    tool_results: list[dict] = field(default_factory=list)
    conversation_summary: str = ""
    tool_results_summary: str = ""
    search_history_summary: str = ""
    memory_summary: str = ""
    cacheable_prefix_version: str = "agent-context-v1"
    dynamic_context_stats: dict = field(default_factory=dict)


class ContextBuilder:
    """Builds model context and only compresses when safety requires it."""

    def build_for_extraction(
        self,
        *,
        message: str,
        parsed_request: ParsedSearchRequest,
        conversation: list[AIChatMessage],
        conversation_summary: str = "",
        tool_results_summary: str = "",
        search_history_summary: str = "",
        memory_summary: str = "",
        force_compress: bool = False,
    ) -> ContextBuildResult:
        latest_message = self._safe_message(message)
        estimated = self._estimate_extraction(
            latest_message=latest_message,
            parsed_request=parsed_request,
            messages=conversation,
            conversation_summary=conversation_summary,
            tool_results_summary=tool_results_summary,
            search_history_summary=search_history_summary,
            memory_summary=memory_summary,
        )
        should_compress, reason = self._should_compress(
            force_compress=force_compress,
            latest_message=message,
            estimated_tokens=estimated,
            tool_results=[],
            search_history=[],
        )
        if not should_compress:
            messages = self._summary_messages(
                conversation_summary=conversation_summary,
                tool_results_summary=tool_results_summary,
                search_history_summary=search_history_summary,
                memory_summary=memory_summary,
            )
            messages.extend(conversation)
            return ContextBuildResult(
                messages=messages,
                latest_message=latest_message,
                estimated_input_tokens=estimated,
                conversation_summary=conversation_summary,
                tool_results_summary=tool_results_summary,
                search_history_summary=search_history_summary,
                memory_summary=memory_summary,
                dynamic_context_stats=self._dynamic_stats(messages, [], []),
            )

        messages = self._compressed_messages(
            conversation=conversation,
            conversation_summary=conversation_summary,
            tool_results_summary=tool_results_summary,
            search_history_summary=search_history_summary,
            memory_summary=memory_summary,
        )
        compressed_latest = self._compress_message(latest_message)
        compressed_estimated = self._estimate_extraction(
            latest_message=compressed_latest,
            parsed_request=parsed_request,
            messages=messages,
            conversation_summary="",
            tool_results_summary="",
            search_history_summary="",
            memory_summary="",
        )
        return ContextBuildResult(
            messages=messages,
            latest_message=compressed_latest,
            estimated_input_tokens=compressed_estimated,
            compressed=True,
            compression_reason=reason,
            conversation_summary=conversation_summary,
            tool_results_summary=tool_results_summary,
            search_history_summary=search_history_summary,
            memory_summary=memory_summary,
            dynamic_context_stats=self._dynamic_stats(messages, [], []),
        )

    def build_for_reply(
        self,
        *,
        parsed_request: ParsedSearchRequest,
        conversation: list[AIChatMessage],
        tool_results: Optional[list[dict]] = None,
        search_history: Optional[list[dict]] = None,
        conversation_summary: str = "",
        tool_results_summary: str = "",
        search_history_summary: str = "",
        memory_summary: str = "",
        force_compress: bool = False,
    ) -> ContextBuildResult:
        tool_results = tool_results or []
        search_history = search_history or []
        effective_tool_summary = tool_results_summary or self.summarize_tool_results(tool_results)
        effective_search_summary = search_history_summary or self.summarize_search_history(search_history)
        estimated = self._estimate_reply(
            parsed_request=parsed_request,
            messages=conversation,
            tool_results=tool_results,
            conversation_summary=conversation_summary,
            tool_results_summary=effective_tool_summary,
            search_history_summary=effective_search_summary,
            memory_summary=memory_summary,
        )
        should_compress, reason = self._should_compress(
            force_compress=force_compress,
            latest_message="",
            estimated_tokens=estimated,
            tool_results=tool_results,
            search_history=search_history,
        )
        if not should_compress:
            messages = self._summary_messages(
                conversation_summary=conversation_summary,
                tool_results_summary=effective_tool_summary,
                search_history_summary=effective_search_summary,
                memory_summary=memory_summary,
            )
            messages.extend(conversation)
            return ContextBuildResult(
                messages=messages,
                latest_message="",
                estimated_input_tokens=estimated,
                tool_results=list(tool_results),
                conversation_summary=conversation_summary,
                tool_results_summary=effective_tool_summary,
                search_history_summary=effective_search_summary,
                memory_summary=memory_summary,
                dynamic_context_stats=self._dynamic_stats(messages, tool_results, search_history),
            )

        summarized_tools = self._summary_tool_payload(effective_tool_summary)
        messages = self._compressed_messages(
            conversation=conversation,
            conversation_summary=conversation_summary,
            tool_results_summary=effective_tool_summary,
            search_history_summary=effective_search_summary,
            memory_summary=memory_summary,
        )
        compressed_estimated = self._estimate_reply(
            parsed_request=parsed_request,
            messages=messages,
            tool_results=summarized_tools,
            conversation_summary="",
            tool_results_summary="",
            search_history_summary="",
            memory_summary="",
        )
        return ContextBuildResult(
            messages=messages,
            latest_message="",
            estimated_input_tokens=compressed_estimated,
            compressed=True,
            compression_reason=reason,
            tool_results=summarized_tools,
            conversation_summary=conversation_summary,
            tool_results_summary=effective_tool_summary,
            search_history_summary=effective_search_summary,
            memory_summary=memory_summary,
            dynamic_context_stats=self._dynamic_stats(messages, summarized_tools, search_history),
        )

    def summarize_conversation(
        self,
        conversation: list[AIChatMessage],
        parsed_request: ParsedSearchRequest,
    ) -> str:
        if not conversation:
            return ""
        latest_user_messages = [item.content for item in conversation if item.role == "user"][-6:]
        latest_assistant_messages = [item.content for item in conversation if item.role == "assistant"][-4:]
        payload = {
            "purpose": "Layover Lens travel planning context summary",
            "current_parameters": parsed_request.model_dump(mode="json"),
            "recent_user_needs": latest_user_messages,
            "recent_assistant_guidance": latest_assistant_messages,
        }
        return self._truncate(json.dumps(payload, ensure_ascii=False), 3500)

    def summarize_tool_results(self, tool_results: list[dict]) -> str:
        if not tool_results:
            return ""
        summaries: list[dict] = []
        for item in tool_results:
            name = str(item.get("name") or "unknown")
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            summary: dict = {
                "name": name,
                "status": item.get("status", "success"),
            }
            if name == "place_search":
                pois = data.get("verified_pois") if isinstance(data, dict) else []
                summary["verified_pois"] = [
                    {
                        "name": poi.get("name"),
                        "city": poi.get("city"),
                        "address": poi.get("address"),
                        "verification_status": poi.get("verification_status"),
                        "provider": poi.get("provider"),
                    }
                    for poi in pois[:5]
                    if isinstance(poi, dict)
                ]
            elif name == "weather_forecast":
                summary["weather"] = {
                    key: data.get(key)
                    for key in ("city", "date", "summary", "temperature_min", "temperature_max", "precipitation_probability")
                    if key in data
                }
            elif name == "date_info":
                summary["date_info"] = {
                    key: data.get(key)
                    for key in ("today", "weekday", "requested_date", "days_from_today")
                    if key in data
                }
            summaries.append(summary)
            summary["content"] = self._truncate(str(item.get("content") or ""), 300)
        return self._truncate(json.dumps(summaries, ensure_ascii=False), settings.ai_agent_context_max_tool_result_chars)

    def summarize_search_history(self, search_history: list[dict]) -> str:
        if not search_history:
            return ""
        summaries: list[dict] = []
        for response in search_history[-3:]:
            recommendations = response.get("recommendations") if isinstance(response, dict) else []
            summaries.append({
                "result_mode": response.get("result_mode") if isinstance(response, dict) else None,
                "recommendations": [
                    {
                        "id": rec.get("id"),
                        "city_path": rec.get("city_path"),
                        "estimated_total_price": rec.get("estimated_total_price"),
                        "estimated_total_duration_minutes": rec.get("estimated_total_duration_minutes"),
                        "confidence": rec.get("confidence"),
                        "warnings": rec.get("warnings", [])[:3],
                    }
                    for rec in recommendations[:5]
                    if isinstance(rec, dict)
                ],
            })
        return self._truncate(json.dumps(summaries, ensure_ascii=False), settings.ai_agent_context_max_search_result_chars)

    def should_refresh_conversation_summary(
        self,
        conversation: list[AIChatMessage],
        *,
        existing_summary: str = "",
        force: bool = False,
    ) -> bool:
        if force:
            return True
        trigger = max(1, settings.ai_agent_context_summary_trigger_messages)
        return bool(conversation) and (len(conversation) >= trigger or bool(existing_summary))

    @staticmethod
    def estimate_tokens(parts: Iterable[str]) -> int:
        total = 0
        for part in parts:
            text = part or ""
            ascii_count = sum(1 for char in text if ord(char) < 128)
            non_ascii_count = len(text) - ascii_count
            total += int(ascii_count / 4) + int(non_ascii_count / 1.5)
        return max(total, 1)

    def _estimate_extraction(
        self,
        *,
        latest_message: str,
        parsed_request: ParsedSearchRequest,
        messages: list[AIChatMessage],
        conversation_summary: str,
        tool_results_summary: str,
        search_history_summary: str,
        memory_summary: str,
    ) -> int:
        return self.estimate_tokens([
            latest_message,
            json.dumps(parsed_request.model_dump(mode="json"), ensure_ascii=False),
            memory_summary,
            conversation_summary,
            tool_results_summary,
            search_history_summary,
            *(item.content for item in messages),
        ])

    def _estimate_reply(
        self,
        *,
        parsed_request: ParsedSearchRequest,
        messages: list[AIChatMessage],
        tool_results: list[dict],
        conversation_summary: str,
        tool_results_summary: str,
        search_history_summary: str,
        memory_summary: str,
    ) -> int:
        return self.estimate_tokens([
            json.dumps(parsed_request.model_dump(mode="json"), ensure_ascii=False),
            json.dumps(tool_results, ensure_ascii=False),
            memory_summary,
            conversation_summary,
            tool_results_summary,
            search_history_summary,
            *(item.content for item in messages),
        ])

    def _should_compress(
        self,
        *,
        force_compress: bool,
        latest_message: str,
        estimated_tokens: int,
        tool_results: list[dict],
        search_history: list[dict],
    ) -> tuple[bool, str]:
        if force_compress:
            return True, "scope_violation"
        if latest_message and len(latest_message) > settings.ai_agent_max_user_message_chars:
            return True, "long_user_message"
        if self._json_size(tool_results) > settings.ai_agent_context_max_tool_result_chars:
            return True, "large_tool_results"
        if self._json_size(search_history) > settings.ai_agent_context_max_search_result_chars:
            return True, "large_search_results"
        hard_limit = settings.ai_agent_context_hard_input_token_limit
        final_limit = settings.ai_agent_context_final_safety_token_limit
        if settings.ai_agent_context_safety_enabled and hard_limit > 0 and estimated_tokens >= hard_limit:
            return True, "context_safety"
        if settings.ai_agent_context_safety_enabled and final_limit > 0 and estimated_tokens >= final_limit:
            return True, "context_safety"
        return False, ""

    def _compressed_messages(
        self,
        *,
        conversation: list[AIChatMessage],
        conversation_summary: str,
        tool_results_summary: str,
        search_history_summary: str,
        memory_summary: str,
    ) -> list[AIChatMessage]:
        messages = self._summary_messages(
            conversation_summary=conversation_summary,
            tool_results_summary=tool_results_summary,
            search_history_summary=search_history_summary,
            memory_summary=memory_summary,
        )
        recent_limit = max(1, settings.ai_agent_context_recent_turns_after_summary)
        messages.extend(conversation[-recent_limit:])
        return messages

    def _summary_messages(
        self,
        *,
        conversation_summary: str,
        tool_results_summary: str,
        search_history_summary: str,
        memory_summary: str,
    ) -> list[AIChatMessage]:
        sections = []
        if memory_summary:
            sections.append(f"Long-term memory summary:\n{memory_summary}")
        if conversation_summary:
            sections.append(f"Conversation summary:\n{conversation_summary}")
        if tool_results_summary:
            sections.append(f"Tool result summary:\n{tool_results_summary}")
        if search_history_summary:
            sections.append(f"Search result summary:\n{search_history_summary}")
        if not sections:
            return []
        return [
            AIChatMessage(
                role="assistant",
                content=self._truncate("\n\n".join(sections), 3900),
            )
        ]

    def _summary_tool_payload(self, tool_results_summary: str) -> list[dict]:
        if not tool_results_summary:
            return []
        return [{
            "name": "context_summary",
            "status": "success",
            "content": self._truncate(tool_results_summary, 1000),
            "data": {"summary": tool_results_summary},
        }]

    @staticmethod
    def _safe_message(message: str) -> str:
        limit = settings.ai_agent_max_user_message_chars
        if limit <= 0 or len(message) <= limit:
            return message
        return message[:limit]

    @staticmethod
    def _compress_message(message: str) -> str:
        limit = min(settings.ai_agent_max_user_message_chars, 1200)
        if len(message) <= limit:
            return message
        head = message[:600]
        tail = message[-400:]
        return f"{head}\n...[message compressed for context safety]...\n{tail}"

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if limit <= 0 or len(text) <= limit:
            return text
        return f"{text[: max(limit - 32, 0)]}...[truncated]"

    @staticmethod
    def _json_size(value: object) -> int:
        if not value:
            return 0
        try:
            return len(json.dumps(value, ensure_ascii=False))
        except TypeError:
            return len(str(value))

    @staticmethod
    def _dynamic_stats(
        messages: list[AIChatMessage],
        tool_results: list[dict],
        search_history: list[dict],
    ) -> dict:
        return {
            "message_count": len(messages),
            "tool_result_count": len(tool_results),
            "search_history_count": len(search_history),
        }
