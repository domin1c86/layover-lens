from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import isclose
from typing import Optional

from app.config import settings
from app.data_source.base import CatalogSnapshot, RouteRecord
from app.schemas import OptimizationTarget


@dataclass(frozen=True)
class PlannedLeg:
    route_id: str
    transport_type: str
    from_city: str
    to_city: str
    from_station: str
    to_station: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    price: float
    company: str
    flight_train_no: str
    departure_at: datetime
    arrival_at: datetime


@dataclass(frozen=True)
class PlannedRoute:
    id: str
    total_price: float
    total_duration_minutes: int
    transfer_count: int
    legs: tuple[PlannedLeg, ...]
    score: Optional[float] = None
    tag: Optional[str] = None


class PythonRoutePlanner:
    def __init__(self) -> None:
        self._max_layover = timedelta(minutes=settings.max_layover_minutes)
        self._max_total_duration = timedelta(minutes=settings.max_total_duration_minutes)

    def plan(
        self,
        *,
        catalog: CatalogSnapshot,
        from_city_code: str,
        to_city_code: str,
        travel_date: date,
        optimization_target: OptimizationTarget,
        max_transfers: int,
        limit: Optional[int] = None,
    ) -> list[PlannedRoute]:
        station_map = {station.code: station for station in catalog.stations}
        city_map = {city.code: city for city in catalog.cities}
        routes_by_city: dict[str, list[RouteRecord]] = {}

        for route in catalog.routes:
            from_station = station_map.get(route.from_station)
            if from_station is None:
                continue
            routes_by_city.setdefault(from_station.city_code, []).append(route)

        for city_routes in routes_by_city.values():
            city_routes.sort(
                key=lambda route: (
                    route.departure_date,
                    route.departure_time,
                    route.arrival_date,
                    route.arrival_time,
                )
            )

        results: list[PlannedRoute] = []
        max_legs = max_transfers + 1

        def dfs(
            current_city: str,
            previous_arrival: Optional[datetime],
            previous_station: Optional[str],
            first_departure: Optional[datetime],
            legs: list[PlannedLeg],
            total_price: float,
            visited_cities: set[str],
        ) -> None:
            if legs and current_city == to_city_code:
                route_departure = first_departure or legs[0].departure_at
                results.append(
                    PlannedRoute(
                        id=f"route_{len(results) + 1}",
                        total_price=round(total_price, 2),
                        total_duration_minutes=int(
                            (legs[-1].arrival_at - route_departure).total_seconds() // 60
                        ),
                        transfer_count=len(legs) - 1,
                        legs=tuple(legs),
                    )
                )
                return

            if len(legs) >= max_legs:
                return

            for route in routes_by_city.get(current_city, []):
                from_station = station_map.get(route.from_station)
                to_station = station_map.get(route.to_station)
                if from_station is None or to_station is None:
                    continue

                departure_at = datetime.combine(route.departure_date, route.departure_time)
                arrival_at = datetime.combine(route.arrival_date, route.arrival_time)

                if previous_arrival is None and route.departure_date != travel_date:
                    continue

                if previous_arrival is not None:
                    transfer_buffer = self._transfer_buffer(previous_station, route.from_station)
                    earliest_departure = previous_arrival + timedelta(minutes=transfer_buffer)
                    if departure_at < earliest_departure:
                        continue
                    if departure_at - previous_arrival > self._max_layover:
                        continue

                effective_departure = first_departure or departure_at
                if arrival_at - effective_departure > self._max_total_duration:
                    continue

                next_city = to_station.city_code
                if next_city in visited_cities and next_city != to_city_code:
                    continue

                leg = PlannedLeg(
                    route_id=route.id,
                    transport_type=route.transport_type,
                    from_city=city_map[from_station.city_code].name,
                    to_city=city_map[next_city].name,
                    from_station=from_station.name,
                    to_station=to_station.name,
                    departure_time=departure_at.strftime("%H:%M"),
                    arrival_time=arrival_at.strftime("%H:%M"),
                    duration_minutes=route.duration_minutes,
                    price=round(route.price, 2),
                    company=route.company,
                    flight_train_no=route.flight_train_no,
                    departure_at=departure_at,
                    arrival_at=arrival_at,
                )

                legs.append(leg)
                next_visited = set(visited_cities)
                next_visited.add(next_city)
                dfs(
                    next_city,
                    arrival_at,
                    route.to_station,
                    effective_departure,
                    legs,
                    total_price + route.price,
                    next_visited,
                )
                legs.pop()

        dfs(from_city_code, None, None, None, [], 0.0, {from_city_code})

        deduped = self._dedupe_routes(results)
        ranked = self._rank_routes(deduped, optimization_target)
        return ranked[:limit] if limit is not None else ranked

    def _transfer_buffer(self, previous_station: Optional[str], next_station: str) -> int:
        if previous_station is None:
            return 0
        if previous_station == next_station:
            return settings.min_transfer_minutes_same_station
        return settings.min_transfer_minutes_same_city

    def _dedupe_routes(self, routes: list[PlannedRoute]) -> list[PlannedRoute]:
        deduped: list[PlannedRoute] = []
        seen: set[tuple[str, ...]] = set()

        for route in routes:
            signature = tuple(
                (
                    f"{leg.route_id}@{leg.departure_at.isoformat()}-"
                    f"{leg.arrival_at.isoformat()}"
                )
                for leg in route.legs
            )
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(route)

        return deduped

    def _rank_routes(
        self,
        routes: list[PlannedRoute],
        optimization_target: OptimizationTarget,
    ) -> list[PlannedRoute]:
        if not routes:
            return []

        if optimization_target == OptimizationTarget.PRICE:
            ranked = sorted(
                routes,
                key=lambda route: (
                    route.total_price,
                    route.total_duration_minutes,
                    route.transfer_count,
                ),
            )
        elif optimization_target == OptimizationTarget.TIME:
            ranked = sorted(
                routes,
                key=lambda route: (
                    route.total_duration_minutes,
                    route.total_price,
                    route.transfer_count,
                ),
            )
        elif optimization_target == OptimizationTarget.TRANSFER:
            ranked = sorted(
                routes,
                key=lambda route: (
                    route.transfer_count,
                    route.total_duration_minutes,
                    route.total_price,
                ),
            )
        else:
            ranked = self._rank_balanced(routes)

        return self._apply_tags(ranked, optimization_target)

    def _rank_balanced(self, routes: list[PlannedRoute]) -> list[PlannedRoute]:
        min_price = min(route.total_price for route in routes)
        max_price = max(route.total_price for route in routes)
        min_duration = min(route.total_duration_minutes for route in routes)
        max_duration = max(route.total_duration_minutes for route in routes)
        min_transfer = min(route.transfer_count for route in routes)
        max_transfer = max(route.transfer_count for route in routes)

        def normalize(value: float, min_value: float, max_value: float) -> float:
            if isclose(max_value, min_value):
                return 1.0
            return 1.0 - ((value - min_value) / (max_value - min_value))

        scored_routes = [
            PlannedRoute(
                id=route.id,
                total_price=route.total_price,
                total_duration_minutes=route.total_duration_minutes,
                transfer_count=route.transfer_count,
                legs=route.legs,
                score=round(
                    normalize(route.total_price, min_price, max_price) * 0.4
                    + normalize(route.total_duration_minutes, min_duration, max_duration) * 0.35
                    + normalize(route.transfer_count, min_transfer, max_transfer) * 0.25,
                    4,
                ),
            )
            for route in routes
        ]

        return sorted(
            scored_routes,
            key=lambda route: (
                -(route.score or 0.0),
                route.total_price,
                route.total_duration_minutes,
            ),
        )

    def _apply_tags(
        self,
        routes: list[PlannedRoute],
        optimization_target: OptimizationTarget,
    ) -> list[PlannedRoute]:
        if not routes:
            return []

        min_price = min(route.total_price for route in routes)
        min_duration = min(route.total_duration_minutes for route in routes)
        min_transfer = min(route.transfer_count for route in routes)
        tagged: list[PlannedRoute] = []

        for index, route in enumerate(routes):
            tag: Optional[str] = None
            if index == 0:
                if optimization_target == OptimizationTarget.PRICE:
                    tag = "价格最低"
                elif optimization_target == OptimizationTarget.TIME:
                    tag = "耗时最短"
                elif optimization_target == OptimizationTarget.TRANSFER:
                    tag = "换乘最少"
                else:
                    tag = "综合推荐"
            elif route.total_price == min_price:
                tag = "价格最低"
            elif route.total_duration_minutes == min_duration:
                tag = "耗时最短"
            elif route.transfer_count == min_transfer:
                tag = "换乘最少"

            tagged.append(
                PlannedRoute(
                    id=route.id,
                    total_price=route.total_price,
                    total_duration_minutes=route.total_duration_minutes,
                    transfer_count=route.transfer_count,
                    legs=route.legs,
                    score=route.score,
                    tag=tag,
                )
            )

        return tagged
