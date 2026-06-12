from __future__ import annotations

import json
from datetime import date
from typing import Optional

from app.config import settings
from app.data_source.base import CatalogSnapshot
from app.schemas import (
    OptimizationTarget,
    RecommendationSegment,
    RouteRecommendation,
    SearchRequest,
    SegmentAvailability,
    TransportType,
)
from app.services.route_planner import _load_cpp_module
from app.services.route_training import select_route_dataset


class CppRouteStrategyPlanner:
    backend_name = "cpp"
    segment_provider = "mock_graph"

    def __init__(self) -> None:
        module = _load_cpp_module()
        if module is None or not hasattr(module, "StrategyPlanner"):
            raise RuntimeError("C++ route strategy planner is required but is not available.")
        self._module = module
        self._native_planner = module.StrategyPlanner()
        self._catalog_id: Optional[int] = None
        self._model_version = "builtin_default"
        self._load_ranker_weights()

    def recommend(
        self,
        *,
        request: SearchRequest,
        catalog: CatalogSnapshot,
        from_city_code: str,
        to_city_code: str,
        source_date: date,
        limit: int | None = None,
    ) -> list[RouteRecommendation]:
        del source_date
        self._load_catalog(catalog)
        native_request = self._build_native_request(
            request=request,
            catalog=catalog,
            from_city_code=from_city_code,
            to_city_code=to_city_code,
            limit=limit,
        )
        return [self._convert_recommendation(item) for item in self._native_planner.recommend(native_request)]

    def _load_catalog(self, catalog: CatalogSnapshot) -> None:
        catalog_id = id(catalog)
        if self._catalog_id == catalog_id:
            return

        cities = []
        for city in catalog.cities:
            item = self._module.StrategyCityInput()
            item.code = city.code
            item.name = city.name
            item.name_en = city.name_en
            cities.append(item)

        stations = []
        for station in catalog.stations:
            item = self._module.StrategyStationInput()
            item.code = station.code
            item.name = station.name
            item.name_en = station.name_en
            item.city_code = station.city_code
            stations.append(item)

        self._native_planner.clear()
        if catalog.segment_edges:
            edges = []
            for edge in catalog.segment_edges:
                item = self._module.SegmentAvailability()
                item.from_city_code = edge.from_city_code
                item.to_city_code = edge.to_city_code
                item.transport_type = self._transport_enum(edge.transport_type)
                item.sample_count = int(edge.sample_count)
                item.estimated_price = float(edge.estimated_price)
                item.estimated_duration_minutes = int(edge.estimated_duration_minutes)
                item.service_frequency_score = float(edge.service_frequency_score)
                item.availability_score = float(edge.availability_score)
                item.confidence = float(edge.confidence)
                item.price_stability_score = float(edge.price_stability_score)
                item.duration_stability_score = float(edge.duration_stability_score)
                item.data_source = edge.data_source
                edges.append(item)
            self._native_planner.load_precomputed_edges(cities, edges)
        else:
            routes = []
            for route in catalog.routes:
                item = self._module.StrategyRouteInput()
                item.id = route.id
                item.from_station = route.from_station
                item.to_station = route.to_station
                item.transport_type = self._transport_enum(route.transport_type)
                item.price = float(route.price)
                item.duration_minutes = int(route.duration_minutes)
                item.data_source = route.platform or "mock_graph"
                routes.append(item)
            self._native_planner.load_catalog(cities, stations, routes)
        self._load_ranker_weights()
        self._catalog_id = catalog_id

    def _build_native_request(
        self,
        *,
        request: SearchRequest,
        catalog: CatalogSnapshot,
        from_city_code: str,
        to_city_code: str,
        limit: int | None,
    ):
        preferred = {transport_type.value for transport_type in request.preferred_transport_types or []}
        native_request = self._module.StrategyRequest()
        native_request.from_city_code = from_city_code
        native_request.to_city_code = to_city_code
        native_request.target = self._target_enum(request.optimization_target)
        native_request.max_transfers = (
            request.max_transfers
            if request.max_transfers is not None
            else settings.default_max_transfers
        )
        native_request.min_transfers = request.min_transfers or 0
        native_request.max_results = limit or settings.max_routes
        native_request.allow_flight = not preferred or TransportType.FLIGHT.value in preferred
        native_request.allow_train = not preferred or TransportType.TRAIN.value in preferred
        native_request.max_price = request.max_price if request.max_price is not None else -1.0
        native_request.max_total_duration_minutes = (
            request.max_total_duration_minutes
            if request.max_total_duration_minutes is not None
            else -1
        )
        native_request.excluded_city_codes = sorted(self._resolve_city_codes(request.excluded_cities, catalog))
        native_request.required_transfer_city_codes = sorted(
            self._resolve_city_codes(request.required_transfer_cities, catalog) - {from_city_code, to_city_code}
        )
        return native_request

    def _convert_recommendation(self, native) -> RouteRecommendation:
        return RouteRecommendation(
            id=native.id,
            city_path=list(native.city_path),
            city_path_en=list(native.city_path_en),
            transfer_cities=list(native.transfer_cities),
            transfer_cities_en=list(native.transfer_cities_en),
            segments=[self._convert_segment(segment) for segment in native.segments],
            estimated_total_price=round(float(native.estimated_total_price), 2),
            estimated_total_duration_minutes=int(native.estimated_total_duration_minutes),
            estimated_price_level=native.estimated_price_level,
            estimated_duration_level=native.estimated_duration_level,
            transfer_count=int(native.transfer_count),
            score=round(float(native.score), 4),
            confidence=round(float(native.confidence), 4),
            reasons=list(native.reasons),
            warnings=list(native.warnings),
            data_sources=list(native.data_sources),
        )

    def _convert_segment(self, native) -> RecommendationSegment:
        availability = native.availability
        return RecommendationSegment(
            from_city=native.from_city,
            to_city=native.to_city,
            from_city_en=native.from_city_en,
            to_city_en=native.to_city_en,
            recommended_transport_type=self._transport_value(native.recommended_transport_type),
            available_transport_types=[
                self._transport_value(transport_type) for transport_type in native.available_transport_types
            ],
            estimated_price=round(float(native.estimated_price), 2),
            estimated_duration_minutes=int(native.estimated_duration_minutes),
            estimated_price_level=native.estimated_price_level,
            estimated_duration_level=native.estimated_duration_level,
            service_frequency_level=native.service_frequency_level,
            availability=SegmentAvailability(
                from_city_code=availability.from_city_code,
                to_city_code=availability.to_city_code,
                transport_type=self._transport_value(availability.transport_type),
                sample_count=int(availability.sample_count),
                estimated_price=round(float(availability.estimated_price), 2),
                estimated_duration_minutes=int(availability.estimated_duration_minutes),
                service_frequency_score=round(float(availability.service_frequency_score), 4),
                availability_score=round(float(availability.availability_score), 4),
                confidence=round(float(availability.confidence), 4),
                price_stability_score=round(float(availability.price_stability_score), 4),
                duration_stability_score=round(float(availability.duration_stability_score), 4),
                data_source=availability.data_source,
            ),
            data_source=native.data_source,
        )

    def _load_ranker_weights(self) -> None:
        selection = select_route_dataset()
        if selection.model_path is None:
            self._model_version = "builtin_default"
            return
        try:
            with selection.model_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self._model_version = "builtin_default"
            return

        native_weights = self._module.StrategyRankerWeights()
        native_weights.version = str(payload.get("version") or "linear_ranker_v1")
        for key, value in (payload.get("weights") or {}).items():
            if hasattr(native_weights, key):
                setattr(native_weights, key, float(value))
        self._native_planner.set_ranker_weights(native_weights)
        self._model_version = native_weights.version

    @property
    def model_version(self) -> str:
        return self._model_version

    def _transport_enum(self, transport_type: str):
        if transport_type == TransportType.FLIGHT.value:
            return self._module.TransportType.FLIGHT
        return self._module.TransportType.TRAIN

    def _transport_value(self, transport_type) -> TransportType:
        if transport_type == self._module.TransportType.FLIGHT:
            return TransportType.FLIGHT
        return TransportType.TRAIN

    def _target_enum(self, target: OptimizationTarget):
        mapping = {
            OptimizationTarget.PRICE: self._module.OptimizeTarget.PRICE,
            OptimizationTarget.TIME: self._module.OptimizeTarget.TIME,
            OptimizationTarget.TRANSFER: self._module.OptimizeTarget.TRANSFER,
            OptimizationTarget.BALANCED: self._module.OptimizeTarget.BALANCED,
        }
        return mapping[target]

    @staticmethod
    def _resolve_city_codes(values: list[str], catalog: CatalogSnapshot) -> set[str]:
        if not values:
            return set()
        by_code = {city.code.upper(): city.code for city in catalog.cities}
        by_name = {city.name: city.code for city in catalog.cities}
        by_name_en = {city.name_en.lower(): city.code for city in catalog.cities if city.name_en}
        resolved: set[str] = set()
        for value in values:
            token = value.strip()
            if token.upper() in by_code:
                resolved.add(by_code[token.upper()])
            elif token in by_name:
                resolved.add(by_name[token])
            elif token.lower() in by_name_en:
                resolved.add(by_name_en[token.lower()])
        return resolved


RouteStrategyService = CppRouteStrategyPlanner


def create_route_strategy_planner() -> CppRouteStrategyPlanner:
    return CppRouteStrategyPlanner()
