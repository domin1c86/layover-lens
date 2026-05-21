from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from math import isclose
from pathlib import Path
from typing import Optional

from app.config import settings
from app.data_source.base import CatalogSnapshot, RouteRecord
from app.schemas import OptimizationTarget


@dataclass(frozen=True)
class PlannedLeg:
    route_id: str
    transport_type: str
    from_city_code: str
    to_city_code: str
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


@dataclass(frozen=True)
class PlanningTimeWindow:
    start_minutes: int
    end_minutes: int

    def contains(self, value_minutes: int) -> bool:
        if self.start_minutes <= self.end_minutes:
            return self.start_minutes <= value_minutes <= self.end_minutes
        return value_minutes >= self.start_minutes or value_minutes <= self.end_minutes


@dataclass(frozen=True)
class PlanningConstraints:
    preferred_transport_types: Optional[frozenset[str]] = None
    max_price: Optional[float] = None
    max_total_duration_minutes: Optional[int] = None
    excluded_city_codes: frozenset[str] = frozenset()
    required_transfer_city_codes: frozenset[str] = frozenset()
    departure_time_range: Optional[PlanningTimeWindow] = None
    arrival_time_range: Optional[PlanningTimeWindow] = None
    allow_overnight: bool = True


def _make_route_identifier(index: int) -> str:
    return f"route_{index + 1}"


def _minutes_since_midnight(moment: datetime) -> int:
    return moment.hour * 60 + moment.minute


def _has_overnight_segment(legs: tuple[PlannedLeg, ...]) -> bool:
    if not legs:
        return False

    if legs[0].departure_at.date() != legs[-1].arrival_at.date():
        return True

    return any(leg.departure_at.date() != leg.arrival_at.date() for leg in legs)


def _route_satisfies_constraints(
    route: PlannedRoute,
    constraints: PlanningConstraints,
) -> bool:
    if constraints.max_price is not None and route.total_price > constraints.max_price:
        return False

    if (
        constraints.max_total_duration_minutes is not None
        and route.total_duration_minutes > constraints.max_total_duration_minutes
    ):
        return False

    if constraints.departure_time_range is not None:
        if not constraints.departure_time_range.contains(
            _minutes_since_midnight(route.legs[0].departure_at)
        ):
            return False

    if constraints.arrival_time_range is not None:
        if not constraints.arrival_time_range.contains(
            _minutes_since_midnight(route.legs[-1].arrival_at)
        ):
            return False

    if not constraints.allow_overnight and _has_overnight_segment(route.legs):
        return False

    if constraints.required_transfer_city_codes:
        transfer_city_codes = {leg.to_city_code for leg in route.legs[:-1]}
        if not constraints.required_transfer_city_codes.issubset(transfer_city_codes):
            return False

    return True


def _apply_tags(
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


class PythonRoutePlanner:
    backend_name = "python"

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
        constraints: Optional[PlanningConstraints] = None,
        limit: Optional[int] = None,
    ) -> list[PlannedRoute]:
        constraints = constraints or PlanningConstraints()
        station_map = {station.code: station for station in catalog.stations}
        city_map = {city.code: city for city in catalog.cities}
        routes_by_city: dict[str, list[RouteRecord]] = {}
        max_total_duration = timedelta(
            minutes=constraints.max_total_duration_minutes
            if constraints.max_total_duration_minutes is not None
            else settings.max_total_duration_minutes
        )

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
                        id=_make_route_identifier(len(results)),
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

                if (
                    constraints.preferred_transport_types is not None
                    and route.transport_type not in constraints.preferred_transport_types
                ):
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
                if arrival_at - effective_departure > max_total_duration:
                    continue

                next_city = to_station.city_code
                if next_city in constraints.excluded_city_codes:
                    continue
                if next_city in visited_cities and next_city != to_city_code:
                    continue

                projected_price = total_price + route.price
                if constraints.max_price is not None and projected_price > constraints.max_price:
                    continue

                leg = PlannedLeg(
                    route_id=route.id,
                    transport_type=route.transport_type,
                    from_city_code=from_station.city_code,
                    to_city_code=next_city,
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
                    projected_price,
                    next_visited,
                )
                legs.pop()

        dfs(from_city_code, None, None, None, [], 0.0, {from_city_code})

        filtered = self._filter_completed_routes(results, constraints)
        deduped = self._dedupe_routes(filtered)
        ranked = self._rank_routes(deduped, optimization_target)
        limited = ranked[:limit] if limit is not None else ranked
        return _apply_tags(limited, optimization_target)

    def _filter_completed_routes(
        self,
        routes: list[PlannedRoute],
        constraints: PlanningConstraints,
    ) -> list[PlannedRoute]:
        filtered: list[PlannedRoute] = []
        for route in routes:
            if not _route_satisfies_constraints(route, constraints):
                continue
            filtered.append(route)
        return filtered

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
            return sorted(
                routes,
                key=lambda route: (
                    route.total_price,
                    route.total_duration_minutes,
                    route.transfer_count,
                ),
            )

        if optimization_target == OptimizationTarget.TIME:
            return sorted(
                routes,
                key=lambda route: (
                    route.total_duration_minutes,
                    route.total_price,
                    route.transfer_count,
                ),
            )

        if optimization_target == OptimizationTarget.TRANSFER:
            return sorted(
                routes,
                key=lambda route: (
                    route.transfer_count,
                    route.total_duration_minutes,
                    route.total_price,
                ),
            )

        return self._rank_balanced(routes)

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


@lru_cache
def _load_cpp_module():
    candidate_paths = [
        Path(__file__).resolve().parents[2] / "planner" / "build",
        Path(__file__).resolve().parents[2],
    ]
    for path in candidate_paths:
        if path.exists():
            path_text = str(path)
            if path_text not in sys.path:
                sys.path.insert(0, path_text)

    try:
        return importlib.import_module("route_planner")
    except ImportError:
        return None


class CppRoutePlanner:
    backend_name = "cpp"

    def __init__(self, module) -> None:
        self._module = module
        self._native_planner = module.PathPlanner()
        self._catalog_id: Optional[int] = None

    def plan(
        self,
        *,
        catalog: CatalogSnapshot,
        from_city_code: str,
        to_city_code: str,
        travel_date: date,
        optimization_target: OptimizationTarget,
        max_transfers: int,
        constraints: Optional[PlanningConstraints] = None,
        limit: Optional[int] = None,
    ) -> list[PlannedRoute]:
        constraints = constraints or PlanningConstraints()
        self._load_catalog(catalog)
        native_routes = self._native_planner.find_routes(
            from_city_code,
            to_city_code,
            travel_date.isoformat(),
            self._target_enum(optimization_target),
            max_transfers,
            limit if limit is not None else settings.max_routes,
            settings.min_transfer_minutes_same_station,
            settings.min_transfer_minutes_same_city,
            settings.max_layover_minutes,
            constraints.max_total_duration_minutes
            if constraints.max_total_duration_minutes is not None
            else settings.max_total_duration_minutes,
            constraints.preferred_transport_types is None
            or "flight" in constraints.preferred_transport_types,
            constraints.preferred_transport_types is None
            or "train" in constraints.preferred_transport_types,
            constraints.max_price if constraints.max_price is not None else -1.0,
            sorted(constraints.excluded_city_codes),
            sorted(constraints.required_transfer_city_codes),
            constraints.departure_time_range.start_minutes
            if constraints.departure_time_range is not None
            else -1,
            constraints.departure_time_range.end_minutes
            if constraints.departure_time_range is not None
            else -1,
            constraints.arrival_time_range.start_minutes
            if constraints.arrival_time_range is not None
            else -1,
            constraints.arrival_time_range.end_minutes
            if constraints.arrival_time_range is not None
            else -1,
            constraints.allow_overnight,
        )

        routes: list[PlannedRoute] = []
        for index, native_route in enumerate(native_routes):
            legs = tuple(self._convert_leg(native_leg) for native_leg in native_route.legs)
            routes.append(
                PlannedRoute(
                    id=_make_route_identifier(index),
                    total_price=round(native_route.total_price, 2),
                    total_duration_minutes=native_route.total_duration_minutes,
                    transfer_count=native_route.transfer_count,
                    legs=legs,
                    score=round(native_route.score, 4)
                    if optimization_target == OptimizationTarget.BALANCED
                    else None,
                )
            )

        return _apply_tags(routes, optimization_target)

    def _load_catalog(self, catalog: CatalogSnapshot) -> None:
        catalog_id = id(catalog)
        if self._catalog_id == catalog_id:
            return

        station_map = {station.code: station for station in catalog.stations}
        city_map = {city.code: city for city in catalog.cities}

        self._native_planner.clear_graph()
        for city in catalog.cities:
            self._native_planner.add_node(city.code)

        for route in catalog.routes:
            from_station = station_map.get(route.from_station)
            to_station = station_map.get(route.to_station)
            if from_station is None or to_station is None:
                continue

            self._native_planner.add_edge(
                from_station.city_code,
                to_station.city_code,
                self._transport_enum(route.transport_type),
                route.id,
                city_map[from_station.city_code].name,
                city_map[to_station.city_code].name,
                from_station.name,
                to_station.name,
                route.departure_date.isoformat(),
                route.departure_time.strftime("%H:%M"),
                route.arrival_date.isoformat(),
                route.arrival_time.strftime("%H:%M"),
                route.duration_minutes,
                float(route.price),
                route.company,
                route.flight_train_no,
            )

        self._catalog_id = catalog_id

    def _convert_leg(self, native_leg) -> PlannedLeg:
        departure_at = datetime.fromisoformat(
            f"{native_leg.departure_date}T{native_leg.departure_time}:00"
        )
        arrival_at = datetime.fromisoformat(
            f"{native_leg.arrival_date}T{native_leg.arrival_time}:00"
        )

        return PlannedLeg(
            route_id=native_leg.route_id,
            transport_type="flight"
            if native_leg.transport_type == self._module.TransportType.FLIGHT
            else "train",
            from_city_code=native_leg.from_node,
            to_city_code=native_leg.to_node,
            from_city=native_leg.from_city,
            to_city=native_leg.to_city,
            from_station=native_leg.from_station,
            to_station=native_leg.to_station,
            departure_time=native_leg.departure_time,
            arrival_time=native_leg.arrival_time,
            duration_minutes=native_leg.duration_minutes,
            price=round(native_leg.price, 2),
            company=native_leg.company,
            flight_train_no=native_leg.flight_train_no,
            departure_at=departure_at,
            arrival_at=arrival_at,
        )

    def _transport_enum(self, transport_type: str):
        if transport_type == "flight":
            return self._module.TransportType.FLIGHT
        return self._module.TransportType.TRAIN

    def _target_enum(self, target: OptimizationTarget):
        mapping = {
            OptimizationTarget.PRICE: self._module.OptimizeTarget.PRICE,
            OptimizationTarget.TIME: self._module.OptimizeTarget.TIME,
            OptimizationTarget.TRANSFER: self._module.OptimizeTarget.TRANSFER,
            OptimizationTarget.BALANCED: self._module.OptimizeTarget.BALANCED,
        }
        return mapping[target]


def create_route_planner(preferred_backend: str = "auto"):
    normalized = preferred_backend.lower()
    cpp_module = _load_cpp_module()

    if normalized == "cpp":
        if cpp_module is None:
            raise RuntimeError("C++ route planner is required but the module could not be imported.")
        return CppRoutePlanner(cpp_module)

    if normalized == "python":
        return PythonRoutePlanner()

    if cpp_module is not None:
        return CppRoutePlanner(cpp_module)

    return PythonRoutePlanner()
