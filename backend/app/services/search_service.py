from __future__ import annotations

from functools import lru_cache
from typing import Optional
from uuid import uuid4

from app.config import settings
from app.data_source import create_data_source
from app.schemas import City, Leg, RoutePlan, SearchRequest, SearchResponse
from app.services.route_planner import PythonRoutePlanner


class SearchService:
    def __init__(self) -> None:
        self._data_source = create_data_source()
        self._planner = PythonRoutePlanner()

    def search(self, request: SearchRequest) -> SearchResponse:
        catalog = self._data_source.get_catalog()
        from_city_code = self._resolve_city_code(request.from_city, catalog.cities)
        to_city_code = self._resolve_city_code(request.to_city, catalog.cities)
        max_transfers = (
            request.max_transfers
            if request.max_transfers is not None
            else settings.default_max_transfers
        )

        planned_routes = self._planner.plan(
            catalog=catalog,
            from_city_code=from_city_code,
            to_city_code=to_city_code,
            travel_date=request.travel_date,
            optimization_target=request.optimization_target,
            max_transfers=max_transfers,
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

    @staticmethod
    def _resolve_city_code(search_value: str, cities: tuple) -> str:
        normalized = search_value.strip().lower()
        for city in cities:
            if normalized in {city.code.lower(), city.name.lower(), city.name_en.lower()}:
                return city.code
        raise ValueError(f"Unknown city: {search_value}")


@lru_cache
def get_search_service() -> SearchService:
    return SearchService()


def reset_search_service_cache() -> None:
    get_search_service.cache_clear()
