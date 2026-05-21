from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class TransportType(str, Enum):
    FLIGHT = "flight"
    TRAIN = "train"


class OptimizationTarget(str, Enum):
    PRICE = "price"
    TIME = "time"
    TRANSFER = "transfer"
    BALANCED = "balanced"


class City(BaseModel):
    code: str
    name: str
    name_en: str = ""
    country: str = "中国"


class CityListResponse(BaseModel):
    cities: list[City]


class TimeRange(BaseModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")

    @field_validator("start", "end")
    @classmethod
    def validate_clock_value(cls, value: str) -> str:
        hours, minutes = [int(part) for part in value.split(":")]
        if hours not in range(24) or minutes not in range(60):
            raise ValueError("Time values must be valid 24-hour clocks.")
        return value


class Leg(BaseModel):
    transport_type: TransportType
    from_city: str
    to_city: str
    from_station: str
    to_station: str
    departure_date: str
    departure_time: str
    arrival_date: str
    arrival_time: str
    duration_minutes: int
    price: float
    company: str
    flight_train_no: str


class RoutePlan(BaseModel):
    id: str
    total_price: float
    total_duration_minutes: int
    transfer_count: int
    legs: list[Leg]
    score: Optional[float] = None
    tag: Optional[str] = None


class SearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_city: str
    to_city: str
    travel_date: date = Field(
        validation_alias=AliasChoices("travel_date", "date"),
    )
    optimization_target: OptimizationTarget = Field(
        default=OptimizationTarget.BALANCED,
        validation_alias=AliasChoices("optimization_target", "optimize"),
    )
    max_transfers: Optional[int] = Field(default=None, ge=0, le=4)
    preferred_transport_types: Optional[list[TransportType]] = None
    max_price: Optional[float] = Field(default=None, ge=0)
    max_total_duration_minutes: Optional[int] = Field(default=None, ge=1)
    excluded_cities: list[str] = Field(default_factory=list)
    required_transfer_cities: list[str] = Field(default_factory=list)
    departure_time_range: Optional[TimeRange] = None
    arrival_time_range: Optional[TimeRange] = None
    allow_overnight: bool = True

    @model_validator(mode="before")
    @classmethod
    def extract_legacy_filters(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        filters = payload.get("filters")
        if isinstance(filters, dict):
            legacy_mapping = {
                "max_transfer": "max_transfers",
                "max_price": "max_price",
                "max_total_duration_minutes": "max_total_duration_minutes",
                "preferred_transport_types": "preferred_transport_types",
                "transport_types": "preferred_transport_types",
                "excluded_cities": "excluded_cities",
                "required_transfer_cities": "required_transfer_cities",
                "departure_time_range": "departure_time_range",
                "arrival_time_range": "arrival_time_range",
                "allow_overnight": "allow_overnight",
            }
            for legacy_key, normalized_key in legacy_mapping.items():
                if legacy_key in filters and normalized_key not in payload:
                    payload[normalized_key] = filters[legacy_key]
        return payload


class SearchResponse(BaseModel):
    search_id: str
    routes: list[RoutePlan]
    total_count: int
    total: int


class ParsedSearchRequest(BaseModel):
    from_city: Optional[str] = None
    to_city: Optional[str] = None
    travel_date: Optional[date] = None
    optimization_target: Optional[OptimizationTarget] = None
    max_transfers: Optional[int] = None
    preferred_transport_types: Optional[list[TransportType]] = None
    max_price: Optional[float] = None
    max_total_duration_minutes: Optional[int] = None
    excluded_cities: list[str] = Field(default_factory=list)
    required_transfer_cities: list[str] = Field(default_factory=list)
    departure_time_range: Optional[TimeRange] = None
    arrival_time_range: Optional[TimeRange] = None
    allow_overnight: Optional[bool] = None


class AIChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class AISearchSessionStatus(str, Enum):
    COLLECTING = "collecting"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"


class AISearchSessionCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class AISearchSessionTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class AISearchSessionConfirmRequest(BaseModel):
    confirmed: bool = True


class AISearchResponse(BaseModel):
    session_id: str
    status: AISearchSessionStatus
    assistant_message: str
    conversation: list[AIChatMessage]
    parsed_request: ParsedSearchRequest
    final_request: Optional[SearchRequest] = None
    missing_fields: list[str]
    summary: str
    ready_for_confirmation: bool
    search_executed: bool
    search_response: Optional[SearchResponse] = None
