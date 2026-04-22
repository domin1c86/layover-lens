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


@dataclass(frozen=True)
class CatalogSnapshot:
    cities: tuple[CityRecord, ...]
    stations: tuple[StationRecord, ...]
    routes: tuple[RouteRecord, ...]


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
