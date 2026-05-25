from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import settings
from app.data_source.base import CityRecord
from app.schemas import AIChatMessage, ParsedSearchRequest


class AIClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class AIConversationTurn:
    assistant_message: str
    extracted_request: dict
    should_confirm: bool
    summary: str


class AIChatClient(Protocol):
    def respond(
        self,
        *,
        conversation: list[AIChatMessage],
        draft_request: ParsedSearchRequest,
        cities: tuple[CityRecord, ...],
    ) -> AIConversationTurn:
        ...


class DeepSeekChatClient:
    def __init__(self) -> None:
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url.rstrip("/")
        self._model = settings.deepseek_model
        self._timeout = settings.deepseek_timeout_seconds

    def respond(
        self,
        *,
        conversation: list[AIChatMessage],
        draft_request: ParsedSearchRequest,
        cities: tuple[CityRecord, ...],
    ) -> AIConversationTurn:
        if not self._api_key:
            raise AIClientError("DeepSeek API key is not configured.")

        city_catalog = ", ".join(
            f"{city.name}({city.code})" for city in cities
        )
        current_draft = json.dumps(
            draft_request.model_dump(mode="json", exclude_none=True),
            ensure_ascii=False,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是 Layover Lens 的多轮搜索助手。你的职责是通过聊天逐步补全用户的路线检索条件，"
                    "优先理解用户偏好，并用简洁自然的中文继续追问缺失或模糊的条件。"
                    "当已具备执行搜索的最低必要字段（from_city, to_city, travel_date）时，"
                    "你还应主动确认预算、交通方式、换乘、时间段、是否过夜、指定中转、排除城市等偏好。"
                    "如果用户尚未提供非必要字段，不要机械地一次性追问所有项，应根据上下文问最有价值的下一问。"
                    "当你认为条件已经足够并且用户偏好已基本明确时，请总结条件并询问用户是否确认开始搜索。"
                    "你必须输出 json 对象，不要输出 markdown。"
                ),
            },
            {
                "role": "system",
                "content": (
                    "可选城市目录如下，优先使用这些城市的中文名作为返回值；如用户输入代码，也要归一化到中文名："
                    f"{city_catalog}。"
                ),
            },
            {
                "role": "system",
                "content": (
                    "当前已收集到的搜索条件 json 为："
                    f"{current_draft}。"
                    "请基于已有条件和对话历史做增量更新，而不是每次重置。"
                ),
            },
            {
                "role": "system",
                "content": (
                    '返回 json 格式必须包含以下字段：'
                    '{"assistant_message": "给用户看的回复", '
                    '"extracted_request": {"from_city": null, "to_city": null, "travel_date": null, '
                    '"optimization_target": null, "max_transfers": null, "preferred_transport_types": null, '
                    '"max_price": null, "max_total_duration_minutes": null, "excluded_cities": [], '
                    '"required_transfer_cities": [], "departure_time_range": null, '
                    '"arrival_time_range": null, "allow_overnight": null}, '
                    '"should_confirm": false, '
                    '"summary": "一句话总结当前理解"}'
                ),
            },
        ]
        messages.extend(
            {"role": message.role, "content": message.content}
            for message in conversation[-settings.ai_search_max_history_messages :]
        )

        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIClientError("DeepSeek request failed.") from exc
        payload = response.json()
        try:
            content = payload["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AIClientError("DeepSeek returned an invalid response payload.") from exc

        return AIConversationTurn(
            assistant_message=str(result.get("assistant_message", "")).strip(),
            extracted_request=result.get("extracted_request") or {},
            should_confirm=bool(result.get("should_confirm", False)),
            summary=str(result.get("summary", "")).strip(),
        )
