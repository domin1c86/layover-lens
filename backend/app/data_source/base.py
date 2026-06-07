from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, time
from typing import Optional


@dataclass(frozen=True)
class CityRecord:
    code: str
    name: str
    name_en: str = ""
    country: str = "中国"


@dataclass(frozen=True)
class StationRecord:
    code: str
    name: str
    city_code: str
    station_type: str
    name_en: str = ""


@dataclass(frozen=True)
class RouteRecord:
    id: str
    from_station: str
    to_station: str
    transport_type: str
    departure_date: date
    departure_time: time
    arrival_date: date
    arrival_time: time
    price: float
    duration_minutes: int
    company: str
    flight_train_no: str
    platform: str = ""


@dataclass(frozen=True)
class SegmentEdgeRecord:
    from_city_code: str
    to_city_code: str
    transport_type: str
    sample_count: int
    estimated_price: float
    estimated_duration_minutes: int
    service_frequency_score: float
    availability_score: float
    confidence: float
    price_stability_score: float = 1.0
    duration_stability_score: float = 1.0
    data_source: str = "historical_csv"


@dataclass(frozen=True)
class CatalogSnapshot:
    cities: tuple[CityRecord, ...]
    stations: tuple[StationRecord, ...]
    routes: tuple[RouteRecord, ...]
    segment_edges: tuple[SegmentEdgeRecord, ...] = ()
    dataset_mode: str = "mock"
    dataset_version: str = "mock"
    model_version: str = "builtin_default"


class DataSourceBase(ABC):
    @abstractmethod
    def get_cities(self, keyword: Optional[str] = None) -> list[CityRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_catalog(self) -> CatalogSnapshot:
        raise NotImplementedError

    @abstractmethod
    def describe_source(self) -> str:
        raise NotImplementedError
