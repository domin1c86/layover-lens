from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from threading import Lock
from typing import Optional
from uuid import uuid4

from app.config import settings
from app.data_source import create_data_source
from app.schemas import (
    AIChatMessage,
    AISearchResponse,
    AISearchSessionStatus,
    City,
    Leg,
    ParsedSearchRequest,
    RoutePlan,
    SearchRequest,
    SearchResponse,
)
from app.services.ai_agent import AIChatClient, AIClientError, DeepSeekChatClient
from app.services.route_planner import (
    PlanningConstraints,
    PlanningTimeWindow,
    create_route_planner,
)


@dataclass
class AISearchSession:
    session_id: str
    conversation: list[AIChatMessage] = field(default_factory=list)
    parsed_request: ParsedSearchRequest = field(default_factory=ParsedSearchRequest)
    summary: str = ""
    assistant_message: str = ""
    status: AISearchSessionStatus = AISearchSessionStatus.COLLECTING
    search_response: Optional[SearchResponse] = None


class SearchService:
    def __init__(self, ai_chat_client: Optional[AIChatClient] = None) -> None:
        self._data_source = create_data_source()
        self._planner = create_route_planner(settings.route_planner_backend)
        self._ai_chat_client = ai_chat_client or DeepSeekChatClient()
        self._ai_sessions: dict[str, AISearchSession] = {}
        self._ai_session_lock = Lock()

    def search(self, request: SearchRequest) -> SearchResponse:
        catalog = self._data_source.get_catalog()
        from_city_code = self._resolve_city_code(request.from_city, catalog.cities)
        to_city_code = self._resolve_city_code(request.to_city, catalog.cities)
        max_transfers = (
            request.max_transfers
            if request.max_transfers is not None
            else settings.default_max_transfers
        )
        constraints = self._build_constraints(
            request=request,
            catalog=catalog,
            from_city_code=from_city_code,
            to_city_code=to_city_code,
        )

        planned_routes = self._planner.plan(
            catalog=catalog,
            from_city_code=from_city_code,
            to_city_code=to_city_code,
            travel_date=request.travel_date,
            optimization_target=request.optimization_target,
            max_transfers=max_transfers,
            constraints=constraints,
            limit=settings.max_routes,
        )

        routes = [
            RoutePlan(
                id=route.id,
                total_price=route.total_price,
                total_duration_minutes=route.total_duration_minutes,
                transfer_count=route.transfer_count,
                score=route.score,
                tag=route.tag,
                legs=[
                    Leg(
                        transport_type=leg.transport_type,
                        from_city=leg.from_city,
                        to_city=leg.to_city,
                        from_station=leg.from_station,
                        to_station=leg.to_station,
                        departure_date=leg.departure_at.strftime("%Y-%m-%d"),
                        departure_time=leg.departure_time,
                        arrival_date=leg.arrival_at.strftime("%Y-%m-%d"),
                        arrival_time=leg.arrival_time,
                        duration_minutes=leg.duration_minutes,
                        price=leg.price,
                        company=leg.company,
                        flight_train_no=leg.flight_train_no,
                    )
                    for leg in route.legs
                ],
            )
            for route in planned_routes
        ]

        return SearchResponse(
            search_id=f"search_{uuid4().hex[:12]}",
            routes=routes,
            total_count=len(routes),
            total=len(routes),
        )

    def list_cities(self, keyword: Optional[str] = None) -> list[City]:
        return [
            City(
                code=city.code,
                name=city.name,
                name_en=city.name_en,
                country=city.country,
            )
            for city in self._data_source.get_cities(keyword)
        ]

    def describe_source(self) -> str:
        return self._data_source.describe_source()

    def describe_planner(self) -> str:
        return getattr(self._planner, "backend_name", "unknown")

    def describe_ai_search(self) -> str:
        return type(self._ai_chat_client).__name__

    def create_ai_session(self, opening_message: str) -> AISearchResponse:
        session = AISearchSession(session_id=f"ai_{uuid4().hex}")
        with self._ai_session_lock:
            self._ai_sessions[session.session_id] = session
        return self.append_ai_message(session.session_id, opening_message)

    def append_ai_message(self, session_id: str, message: str) -> AISearchResponse:
        session = self._get_ai_session(session_id)
        if session.status == AISearchSessionStatus.COMPLETED:
            return self._build_ai_response(session)

        session.conversation.append(AIChatMessage(role="user", content=message))
        catalog = self._data_source.get_catalog()
        try:
            turn = self._ai_chat_client.respond(
                conversation=session.conversation,
                draft_request=session.parsed_request,
                cities=catalog.cities,
            )
        except AIClientError:
            raise
        except Exception as exc:  # pragma: no cover - defensive adapter boundary
            raise AIClientError("DeepSeek request failed.") from exc

        session.parsed_request = self._merge_parsed_request(
            session.parsed_request,
            turn.extracted_request,
            catalog.cities,
        )
        missing_fields = self._missing_ai_fields(session.parsed_request)
        final_request = self._build_final_ai_request(session.parsed_request)
        ready_for_confirmation = final_request is not None

        session.assistant_message = turn.assistant_message or self._default_follow_up(missing_fields)
        session.summary = turn.summary or self._build_ai_summary(session.parsed_request, missing_fields)
        session.status = (
            AISearchSessionStatus.AWAITING_CONFIRMATION
            if ready_for_confirmation
            else AISearchSessionStatus.COLLECTING
        )
        session.conversation.append(
            AIChatMessage(role="assistant", content=session.assistant_message)
        )
        return self._build_ai_response(session)

    def confirm_ai_session(self, session_id: str, *, confirmed: bool) -> AISearchResponse:
        session = self._get_ai_session(session_id)
        if session.status == AISearchSessionStatus.COMPLETED:
            return self._build_ai_response(session)

        final_request = self._build_final_ai_request(session.parsed_request)
        if final_request is None:
            raise ValueError("AI session is not ready for confirmation.")

        if not confirmed:
            session.status = AISearchSessionStatus.COLLECTING
            session.assistant_message = "好的，我们继续调整条件。你最想先改哪一项？"
            session.conversation.append(
                AIChatMessage(role="assistant", content=session.assistant_message)
            )
            return self._build_ai_response(session)

        session.search_response = self.search(final_request)
        session.assistant_message = "已按确认条件完成搜索。"
        session.summary = self._build_ai_summary(session.parsed_request, [])
        session.status = AISearchSessionStatus.COMPLETED
        session.conversation.append(
            AIChatMessage(role="assistant", content=session.assistant_message)
        )
        return self._build_ai_response(session)

    def get_ai_session(self, session_id: str) -> AISearchResponse:
        return self._build_ai_response(self._get_ai_session(session_id))

    def _get_ai_session(self, session_id: str) -> AISearchSession:
        with self._ai_session_lock:
            session = self._ai_sessions.get(session_id)
        if session is None:
            raise ValueError(f"Unknown AI session: {session_id}")
        return session

    @staticmethod
    def _resolve_city_code(search_value: str, cities: tuple) -> str:
        normalized = search_value.strip().lower()
        for city in cities:
            if normalized in {city.code.lower(), city.name.lower(), city.name_en.lower()}:
                return city.code
        raise ValueError(f"Unknown city: {search_value}")

    def _resolve_city_codes(self, search_values: list[str], cities: tuple) -> set[str]:
        resolved: set[str] = set()
        for value in search_values:
            resolved.add(self._resolve_city_code(value, cities))
        return resolved

    def _normalize_city_name(self, value: str, cities: tuple) -> str:
        normalized = value.strip().lower()
        for city in cities:
            if normalized in {city.code.lower(), city.name.lower(), city.name_en.lower()}:
                return city.name
        return value.strip()

    def _merge_parsed_request(
        self,
        current: ParsedSearchRequest,
        patch_payload: dict,
        cities: tuple,
    ) -> ParsedSearchRequest:
        patch = ParsedSearchRequest.model_validate(patch_payload)
        merged_payload = current.model_dump(mode="python")
        patch_data = patch.model_dump(mode="python", exclude_none=True)

        list_fields = {"excluded_cities", "required_transfer_cities"}
        for key, value in patch_data.items():
            if key in list_fields:
                existing = merged_payload.get(key) or []
                merged_payload[key] = self._merge_unique(existing, value)
            else:
                merged_payload[key] = value

        merged = ParsedSearchRequest.model_validate(merged_payload)
        for field_name in ("from_city", "to_city"):
            city_name = getattr(merged, field_name)
            if city_name:
                setattr(merged, field_name, self._normalize_city_name(city_name, cities))

        merged.excluded_cities = [
            self._normalize_city_name(city_name, cities) for city_name in merged.excluded_cities
        ]
        merged.required_transfer_cities = [
            self._normalize_city_name(city_name, cities)
            for city_name in merged.required_transfer_cities
        ]
        return merged

    @staticmethod
    def _merge_unique(existing: list[str], incoming: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in [*existing, *incoming]:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    @staticmethod
    def _missing_ai_fields(parsed_request: ParsedSearchRequest) -> list[str]:
        missing: list[str] = []
        if not parsed_request.from_city:
            missing.append("from_city")
        if not parsed_request.to_city:
            missing.append("to_city")
        if not parsed_request.travel_date:
            missing.append("travel_date")
        return missing

    def _build_final_ai_request(
        self,
        parsed_request: ParsedSearchRequest,
    ) -> Optional[SearchRequest]:
        if self._missing_ai_fields(parsed_request):
            return None

        payload = parsed_request.model_dump(mode="python", exclude_none=True)
        payload.setdefault("optimization_target", "balanced")
        payload.setdefault("allow_overnight", True)
        return SearchRequest.model_validate(payload)

    def _build_constraints(
        self,
        *,
        request: SearchRequest,
        catalog,
        from_city_code: str,
        to_city_code: str,
    ) -> PlanningConstraints:
        excluded_city_codes = self._resolve_city_codes(request.excluded_cities, catalog.cities)
        required_transfer_city_codes = self._resolve_city_codes(
            request.required_transfer_cities,
            catalog.cities,
        )

        return PlanningConstraints(
            preferred_transport_types=(
                frozenset(transport_type.value for transport_type in request.preferred_transport_types)
                if request.preferred_transport_types
                else None
            ),
            max_price=request.max_price,
            max_total_duration_minutes=request.max_total_duration_minutes,
            excluded_city_codes=frozenset(excluded_city_codes),
            required_transfer_city_codes=frozenset(required_transfer_city_codes)
            - {from_city_code, to_city_code},
            departure_time_range=self._build_time_window(request.departure_time_range),
            arrival_time_range=self._build_time_window(request.arrival_time_range),
            allow_overnight=request.allow_overnight,
        )

    @staticmethod
    def _build_time_window(time_range) -> Optional[PlanningTimeWindow]:
        if time_range is None:
            return None

        def to_minutes(value: str) -> int:
            hours, minutes = [int(part) for part in value.split(":")]
            return hours * 60 + minutes

        return PlanningTimeWindow(
            start_minutes=to_minutes(time_range.start),
            end_minutes=to_minutes(time_range.end),
        )

    def _build_ai_response(self, session: AISearchSession) -> AISearchResponse:
        final_request = self._build_final_ai_request(session.parsed_request)
        missing_fields = self._missing_ai_fields(session.parsed_request)
        ready_for_confirmation = final_request is not None
        return AISearchResponse(
            session_id=session.session_id,
            status=session.status,
            assistant_message=session.assistant_message,
            conversation=session.conversation,
            parsed_request=session.parsed_request,
            final_request=final_request,
            missing_fields=missing_fields,
            summary=session.summary or self._build_ai_summary(session.parsed_request, missing_fields),
            ready_for_confirmation=ready_for_confirmation,
            search_executed=session.search_response is not None,
            search_response=session.search_response,
        )

    def _build_ai_summary(
        self,
        parsed_request: ParsedSearchRequest,
        missing_fields: list[str],
    ) -> str:
        parts: list[str] = []
        if parsed_request.from_city:
            parts.append(f"出发地：{parsed_request.from_city}")
        if parsed_request.to_city:
            parts.append(f"目的地：{parsed_request.to_city}")
        if parsed_request.travel_date:
            parts.append(f"日期：{parsed_request.travel_date.isoformat()}")
        if parsed_request.optimization_target:
            parts.append(f"排序：{parsed_request.optimization_target.value}")
        if parsed_request.max_price is not None:
            parts.append(f"预算上限：{parsed_request.max_price:.0f}")
        if parsed_request.max_transfers is not None:
            parts.append(f"最多换乘：{parsed_request.max_transfers}")
        if parsed_request.preferred_transport_types:
            parts.append(
                "交通方式："
                + ",".join(transport_type.value for transport_type in parsed_request.preferred_transport_types)
            )
        if parsed_request.required_transfer_cities:
            parts.append("指定中转：" + ",".join(parsed_request.required_transfer_cities))
        if parsed_request.excluded_cities:
            parts.append("排除城市：" + ",".join(parsed_request.excluded_cities))
        if parsed_request.departure_time_range:
            parts.append(
                "出发时段："
                f"{parsed_request.departure_time_range.start}-{parsed_request.departure_time_range.end}"
            )
        if parsed_request.arrival_time_range:
            parts.append(
                "到达时段："
                f"{parsed_request.arrival_time_range.start}-{parsed_request.arrival_time_range.end}"
            )
        if parsed_request.allow_overnight is False:
            parts.append("限制：不允许过夜")

        if missing_fields:
            return "已收集部分条件，仍缺少：" + ", ".join(missing_fields)
        if parts:
            return "当前条件：" + "；".join(parts)
        return "尚未形成可执行的搜索条件。"

    @staticmethod
    def _default_follow_up(missing_fields: list[str]) -> str:
        if not missing_fields:
            return "我已经整理好搜索条件了。请确认是否开始检索。"
        field_labels = {
            "from_city": "出发城市",
            "to_city": "目的地",
            "travel_date": "出发日期",
        }
        next_field = field_labels.get(missing_fields[0], missing_fields[0])
        return f"我还需要确认{next_field}，你可以直接告诉我。"


@lru_cache
def get_search_service() -> SearchService:
    return SearchService()


def reset_search_service_cache() -> None:
    get_search_service.cache_clear()
