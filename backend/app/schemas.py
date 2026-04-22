from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


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

    @model_validator(mode="before")
    @classmethod
    def extract_legacy_filters(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        filters = payload.get("filters")
        if isinstance(filters, dict) and "max_transfer" in filters and "max_transfers" not in payload:
            payload["max_transfers"] = filters["max_transfer"]
        return payload


class SearchResponse(BaseModel):
    search_id: str
    routes: list[RoutePlan]
    total_count: int
    total: int
