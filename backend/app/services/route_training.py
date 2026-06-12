from __future__ import annotations

import csv
import gzip
import json
import re
import time
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from typing import Iterable
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET

from app.config import settings
from app.data_source.base import CatalogSnapshot, CityRecord, SegmentEdgeRecord, StationRecord

ARTIFACT_SCHEMA_VERSION = 1
DEFAULT_MODEL_VERSION = "builtin_default"
DEFAULT_MODEL_FILENAME = "linear_ranker_v1.json"
DEFAULT_ARTIFACT_FILENAME = "route_edges_v1.json.gz"
MAX_REASONABLE_SEGMENT_MINUTES = 72 * 60


@dataclass(frozen=True)
class RouteTrainingPaths:
    root: Path
    raw_csv: Path
    artifacts: Path
    models: Path

    @property
    def default_artifact(self) -> Path:
        return self.artifacts / DEFAULT_ARTIFACT_FILENAME

    @property
    def default_model(self) -> Path:
        return self.models / DEFAULT_MODEL_FILENAME


@dataclass(frozen=True)
class RouteDatasetSelection:
    mode: str
    has_csv: bool
    artifact_path: Path | None
    model_path: Path | None
    dataset_version: str
    model_version: str
    warning: str = ""


@dataclass(frozen=True)
class RouteTrainingBuildResult:
    dataset_version: str
    model_version: str
    source_rows: int
    accepted_rows: int
    rejected_rows: int
    edge_count: int
    artifact_path: Path
    model_path: Path


@dataclass
class RouteTrainingStats:
    csv_files: list[str]
    xlsx_files: list[str]
    csv_rows: int = 0
    csv_accepted_rows: int = 0
    csv_rejected_rows: int = 0
    excel_train_count: int = 0
    excel_stop_rows: int = 0
    excel_expanded_segments: int = 0
    excel_accepted_segments: int = 0
    excel_rejected_segments: int = 0
    unmapped_station_count: int = 0
    station_mapping_conflicts: int = 0
    missing_price_count: int = 0
    missing_duration_count: int = 0
    normalized_code_count: int = 0
    err_code_count: int = 0
    template_only_edge_count: int = 0
    train_edge_count: int = 0
    flight_edge_count: int = 0
    low_confidence_edge_count: int = 0
    alias_merged_city_count: int = 0
    alias_self_loop_dropped_count: int = 0
    unmapped_station_counts: dict[str, int] | None = None
    code_error_counts: dict[str, int] | None = None
    station_mapping_conflict_examples: list[dict] | None = None
    city_alias_merge_examples: list[dict] | None = None


def route_training_paths() -> RouteTrainingPaths:
    configured = Path(settings.route_training_data_dir)
    if configured.is_absolute():
        root = configured
    else:
        backend_root = Path(__file__).resolve().parents[2]
        parts = configured.parts
        if parts and parts[0] == "backend":
            root = backend_root.joinpath(*parts[1:])
        else:
            root = backend_root / configured
    return RouteTrainingPaths(
        root=root,
        raw_csv=root / "raw_csv",
        artifacts=root / "artifacts",
        models=root / "models",
    )


def ensure_route_training_dirs() -> RouteTrainingPaths:
    paths = route_training_paths()
    for directory in (paths.raw_csv, paths.artifacts, paths.models):
        directory.mkdir(parents=True, exist_ok=True)
    return paths


def select_route_dataset() -> RouteDatasetSelection:
    paths = ensure_route_training_dirs()
    csv_files = sorted(paths.raw_csv.glob("*.csv"))
    xlsx_files = sorted(paths.raw_csv.glob("*.xlsx"))
    mode = settings.route_dataset_mode.lower()
    if mode not in {"auto", "mock", "historical"}:
        mode = "auto"

    has_artifact = paths.default_artifact.exists()
    has_model = paths.default_model.exists()
    has_raw_data = bool(csv_files or xlsx_files)
    if mode == "mock" or (mode == "auto" and not has_raw_data and not has_artifact):
        return RouteDatasetSelection(
            mode="mock",
            has_csv=has_raw_data,
            artifact_path=None,
            model_path=None,
            dataset_version="mock",
            model_version=DEFAULT_MODEL_VERSION,
        )

    if not has_artifact:
        return RouteDatasetSelection(
            mode="mock",
            has_csv=has_raw_data,
            artifact_path=None,
            model_path=None,
            dataset_version="mock",
            model_version=DEFAULT_MODEL_VERSION,
            warning="route_training_raw_data_present_without_artifact",
        )

    metadata = read_artifact_metadata(paths.default_artifact)
    model_version = DEFAULT_MODEL_VERSION
    if has_model:
        model_version = read_model_version(paths.default_model)
    return RouteDatasetSelection(
        mode="historical",
        has_csv=has_raw_data,
        artifact_path=paths.default_artifact,
        model_path=paths.default_model if has_model else None,
        dataset_version=metadata.get("dataset_version", "historical_unknown"),
        model_version=model_version,
        warning="" if has_model else "route_training_model_missing_using_builtin_weights",
    )


def read_artifact_metadata(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    return {
        "schema_version": payload.get("schema_version"),
        "dataset_version": payload.get("dataset_version"),
        "generated_at": payload.get("generated_at"),
        "edge_count": len(payload.get("edges", [])),
        "training_metadata": payload.get("training_metadata", {}),
    }


def validate_route_training_artifact() -> dict:
    selection = select_route_dataset()
    if selection.artifact_path is None:
        return {
            "status": "missing_artifact",
            "mode": selection.mode,
            "dataset_version": selection.dataset_version,
            "model_version": selection.model_version,
            "warnings": [selection.warning] if selection.warning else ["route_training_artifact_missing"],
        }
    payload = _load_artifact_payload(selection.artifact_path)
    edges = payload.get("edges", [])
    metadata = payload.get("training_metadata", {})
    warnings = []
    if metadata.get("unmapped_station_count", 0) > 0:
        warnings.append("unmapped_train_stations_present")
    if metadata.get("err_code_count", 0) > 0:
        warnings.append("vehicle_code_errors_present")
    if metadata.get("template_only_edge_count", 0) > 0:
        warnings.append("template_only_edges_present")
    if metadata.get("low_confidence_edge_count", 0) > 0:
        warnings.append("low_confidence_edges_present")
    return {
        "status": "ok",
        "dataset_version": payload.get("dataset_version", selection.dataset_version),
        "model_version": selection.model_version,
        "edge_count": len(edges),
        "city_count": len(payload.get("cities", [])),
        "station_count": len(payload.get("stations", [])),
        "train_edge_count": metadata.get("train_edge_count", 0),
        "flight_edge_count": metadata.get("flight_edge_count", 0),
        "low_confidence_edge_count": metadata.get("low_confidence_edge_count", 0),
        "template_only_edge_count": metadata.get("template_only_edge_count", 0),
        "missing_price_count": metadata.get("missing_price_count", 0),
        "missing_duration_count": metadata.get("missing_duration_count", 0),
        "top_unmapped_stations": metadata.get("top_unmapped_stations", []),
        "code_error_sources": metadata.get("code_error_sources", []),
        "station_mapping_conflict_examples": metadata.get("station_mapping_conflict_examples", []),
        "city_alias_merge_examples": metadata.get("city_alias_merge_examples", []),
        "warnings": warnings,
    }


def evaluate_route_training_artifact() -> dict:
    selection = select_route_dataset()
    if selection.artifact_path is None:
        return {
            "status": "missing_artifact",
            "mode": selection.mode,
            "warnings": [selection.warning] if selection.warning else ["route_training_artifact_missing"],
            "benchmarks": [],
        }

    from app.schemas import OptimizationTarget, SearchRequest, TransportType
    from app.services.route_strategy import CppRouteStrategyPlanner

    catalog = load_historical_catalog(selection.artifact_path)
    benchmarks = _build_evaluation_benchmarks(catalog)
    planner = CppRouteStrategyPlanner()
    edge_price: dict[tuple[str, str], float] = {}
    for edge in catalog.segment_edges:
        key = (edge.from_city_code, edge.to_city_code)
        edge_price[key] = min(edge_price.get(key, edge.estimated_price), edge.estimated_price)
    results = []
    total_price = 0.0
    total_duration = 0
    total_transfers = 0
    low_confidence = 0
    direct_guard_violations = 0
    result_count = 0
    for benchmark in benchmarks:
        for target in (
            OptimizationTarget.BALANCED,
            OptimizationTarget.PRICE,
            OptimizationTarget.TIME,
            OptimizationTarget.TRANSFER,
        ):
            preferred = []
            if benchmark["transport_type"] == "train":
                preferred = [TransportType.TRAIN]
            elif benchmark["transport_type"] == "flight":
                preferred = [TransportType.FLIGHT]
            request = SearchRequest(
                from_city=benchmark["from_city_name"],
                to_city=benchmark["to_city_name"],
                travel_date=date.today(),
                optimization_target=target,
                max_transfers=benchmark["max_transfers"],
                preferred_transport_types=preferred,
            )
            recommendations = planner.recommend(
                request=request,
                catalog=catalog,
                from_city_code=benchmark["from_city_code"],
                to_city_code=benchmark["to_city_code"],
                source_date=date.today(),
                limit=3,
            )
            top = recommendations[0] if recommendations else None
            if top:
                result_count += 1
                total_price += float(top.estimated_total_price)
                total_duration += int(top.estimated_total_duration_minutes)
                total_transfers += int(top.transfer_count)
                if top.confidence < 0.35:
                    low_confidence += 1
                direct_price = edge_price.get((benchmark["from_city_code"], benchmark["to_city_code"]))
                if direct_price and top.transfer_count > 0 and top.estimated_total_price > direct_price * 1.25:
                    direct_guard_violations += 1
            results.append(
                {
                    "case": benchmark["case"],
                    "target": target.value,
                    "has_result": bool(top),
                    "top_path": top.city_path if top else [],
                    "top_price": top.estimated_total_price if top else None,
                    "top_duration_minutes": top.estimated_total_duration_minutes if top else None,
                    "top_transfer_count": top.transfer_count if top else None,
                    "top_confidence": top.confidence if top else None,
                }
            )
    total_cases = len(results)
    return {
        "status": "ok",
        "dataset_version": catalog.dataset_version,
        "model_version": selection.model_version,
        "case_count": total_cases,
        "result_rate": round(result_count / total_cases, 4) if total_cases else 0,
        "average_price": round(total_price / result_count, 2) if result_count else None,
        "average_duration_minutes": round(total_duration / result_count, 2) if result_count else None,
        "average_transfer_count": round(total_transfers / result_count, 4) if result_count else None,
        "low_confidence_recommendation_ratio": round(low_confidence / result_count, 4) if result_count else 0,
        "direct_guard_violation_count": direct_guard_violations,
        "benchmarks": results,
    }


def read_model_version(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return str(payload.get("version") or DEFAULT_MODEL_VERSION)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_MODEL_VERSION


def load_historical_catalog(path: Path) -> CatalogSnapshot:
    payload = _load_artifact_payload(path)
    cities = tuple(
        CityRecord(
            code=item["code"],
            name=item.get("name") or item["code"],
            name_en=item.get("name_en") or item.get("name") or item["code"],
            country=item.get("country", "China"),
        )
        for item in payload.get("cities", [])
    )
    stations = tuple(
        StationRecord(
            code=item["code"],
            name=item.get("name") or item["code"],
            name_en=item.get("name_en") or item.get("name") or item["code"],
            city_code=item["city_code"],
            station_type=item.get("station_type", "unknown"),
        )
        for item in payload.get("stations", [])
    )
    edges = tuple(
        SegmentEdgeRecord(
            from_city_code=item["from_city_code"],
            to_city_code=item["to_city_code"],
            transport_type=item["transport_type"],
            sample_count=int(item["sample_count"]),
            estimated_price=float(item["estimated_price"]),
            estimated_duration_minutes=int(item["estimated_duration_minutes"]),
            service_frequency_score=float(item["service_frequency_score"]),
            availability_score=float(item["availability_score"]),
            confidence=float(item["confidence"]),
            price_stability_score=float(item.get("price_stability_score", 1.0)),
            duration_stability_score=float(item.get("duration_stability_score", 1.0)),
            data_source=item.get("data_source", "historical_csv"),
        )
        for item in payload.get("edges", [])
    )
    return CatalogSnapshot(
        cities=cities,
        stations=stations,
        routes=(),
        segment_edges=edges,
        dataset_mode="historical",
        dataset_version=payload.get("dataset_version", "historical_unknown"),
        model_version=read_model_version(route_training_paths().default_model),
    )


def _load_artifact_payload(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def _replace_generated_file(source: Path, target: Path) -> None:
    last_error: PermissionError | None = None
    for _ in range(8):
        try:
            source.replace(target)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.25)
    backup = target.with_suffix(target.suffix + ".bak")
    try:
        if backup.exists():
            backup.unlink()
        if target.exists():
            target.rename(backup)
        source.replace(target)
    except PermissionError:
        try:
            with source.open("rb") as source_handle, target.open("r+b") as target_handle:
                target_handle.seek(0)
                while True:
                    chunk = source_handle.read(1024 * 1024)
                    if not chunk:
                        break
                    target_handle.write(chunk)
                target_handle.truncate()
            try:
                source.unlink()
            except OSError:
                pass
            return
        except OSError:
            if last_error is not None:
                raise last_error
            raise
    finally:
        try:
            if backup.exists():
                backup.unlink()
        except OSError:
            pass


def _build_evaluation_benchmarks(catalog: CatalogSnapshot) -> list[dict]:
    cities = {city.code: city for city in catalog.cities}
    by_transport: dict[str, list[SegmentEdgeRecord]] = {"train": [], "flight": []}
    for edge in catalog.segment_edges:
        if edge.from_city_code in cities and edge.to_city_code in cities:
            by_transport.setdefault(edge.transport_type, []).append(edge)
    for edges in by_transport.values():
        edges.sort(key=lambda item: (-item.sample_count, -item.confidence, item.estimated_price))

    benchmarks: list[dict] = []
    for transport_type in ("train", "flight"):
        if by_transport.get(transport_type):
            edge = by_transport[transport_type][0]
            benchmarks.append(_benchmark_from_edge(f"{transport_type}_direct", edge, cities, transport_type, 0))

    transfer_case = _find_transfer_benchmark(catalog, cities)
    if transfer_case:
        benchmarks.append(transfer_case)
    if not benchmarks and catalog.segment_edges:
        benchmarks.append(_benchmark_from_edge("direct", catalog.segment_edges[0], cities, "", 0))
    return benchmarks[:4]


def _benchmark_from_edge(
    case: str,
    edge: SegmentEdgeRecord,
    cities: dict[str, CityRecord],
    transport_type: str,
    max_transfers: int,
) -> dict:
    from_city = cities[edge.from_city_code]
    to_city = cities[edge.to_city_code]
    return {
        "case": case,
        "from_city_code": edge.from_city_code,
        "to_city_code": edge.to_city_code,
        "from_city_name": from_city.name_en or from_city.name,
        "to_city_name": to_city.name_en or to_city.name,
        "transport_type": transport_type,
        "max_transfers": max_transfers,
    }


def _find_transfer_benchmark(catalog: CatalogSnapshot, cities: dict[str, CityRecord]) -> dict | None:
    outgoing: dict[str, list[SegmentEdgeRecord]] = {}
    direct_pairs = {(edge.from_city_code, edge.to_city_code) for edge in catalog.segment_edges}
    for edge in catalog.segment_edges:
        outgoing.setdefault(edge.from_city_code, []).append(edge)
    for first in sorted(catalog.segment_edges, key=lambda item: (-item.sample_count, item.estimated_price))[:2000]:
        for second in outgoing.get(first.to_city_code, [])[:50]:
            if first.from_city_code == second.to_city_code:
                continue
            if (first.from_city_code, second.to_city_code) in direct_pairs:
                continue
            if first.from_city_code in cities and second.to_city_code in cities:
                benchmark = _benchmark_from_edge("one_transfer", first, cities, "", 1)
                benchmark["to_city_code"] = second.to_city_code
                benchmark["to_city_name"] = cities[second.to_city_code].name_en or cities[second.to_city_code].name
                return benchmark
    return None


def build_route_training_artifacts() -> RouteTrainingBuildResult:
    paths = ensure_route_training_dirs()
    csv_files = sorted(paths.raw_csv.glob("*.csv"))
    xlsx_files = sorted(paths.raw_csv.glob("*.xlsx"))
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    dataset_version = "historical_" + generated_at.replace(":", "").replace("-", "")

    cities: dict[str, dict] = {}
    stations: dict[str, dict] = {}
    buckets: dict[tuple[str, str, str], dict] = {}
    station_city_votes: dict[str, dict[str, dict]] = {}
    seen: set[tuple[str, str, str, str, str, str]] = set()
    stats = RouteTrainingStats(
        csv_files=[file.name for file in csv_files],
        xlsx_files=[file.name for file in xlsx_files],
    )
    stats.unmapped_station_counts = {}
    stats.code_error_counts = {}
    stats.station_mapping_conflict_examples = []
    stats.city_alias_merge_examples = []

    for csv_file in csv_files:
        with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                stats.csv_rows += 1
                try:
                    normalized = _normalize_ticket_row(row, stats)
                except ValueError:
                    stats.csv_rejected_rows += 1
                    continue
                signature = (
                    str(normalized["from_station"]),
                    str(normalized["to_station"]),
                    str(normalized["transport_type"]),
                    str(normalized["departure_date"]),
                    str(normalized["departure_time"]),
                    str(normalized["flight_train_no"]),
                )
                if signature in seen:
                    continue
                seen.add(signature)
                stats.csv_accepted_rows += 1
                _register_city_pair(cities, normalized)
                _register_station_pair(stations, normalized)
                _record_station_mapping(station_city_votes, normalized, "from")
                _record_station_mapping(station_city_votes, normalized, "to")
                _add_edge_sample(
                    buckets,
                    str(normalized["from_city_code"]),
                    str(normalized["to_city_code"]),
                    str(normalized["transport_type"]),
                    price=normalized["price"],
                    duration_minutes=normalized["duration_minutes"],
                    data_source=str(normalized["data_source"]),
                    is_template=False,
                )

    station_city_map = _finalize_station_city_map(station_city_votes, stats)
    for xlsx_file in xlsx_files:
        _process_train_line_workbook(
            xlsx_file=xlsx_file,
            station_city_map=station_city_map,
            cities=cities,
            stations=stations,
            buckets=buckets,
            stats=stats,
        )

    _canonicalize_city_graph(cities, stations, buckets, stats)
    edges = [
        _build_edge(from_city_code, to_city_code, transport_type, bucket)
        for (from_city_code, to_city_code, transport_type), bucket in sorted(buckets.items())
    ]
    _record_edge_quality_stats(edges, stats)
    accepted_rows = stats.csv_accepted_rows + stats.excel_accepted_segments
    rejected_rows = stats.csv_rejected_rows + stats.excel_rejected_segments
    artifact_payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "generated_at": generated_at,
        "source_files": [*stats.csv_files, *stats.xlsx_files],
        "source_csv_files": stats.csv_files,
        "source_xlsx_files": stats.xlsx_files,
        "source_rows": stats.csv_rows,
        "accepted_rows": accepted_rows,
        "rejected_rows": rejected_rows,
        "training_metadata": _stats_payload(stats),
        "cities": sorted(cities.values(), key=lambda item: item["code"]),
        "stations": sorted(stations.values(), key=lambda item: item["code"]),
        "edges": edges,
    }
    artifact_tmp = paths.default_artifact.with_suffix(paths.default_artifact.suffix + ".tmp")
    with gzip.open(artifact_tmp, "wt", encoding="utf-8") as handle:
        json.dump(artifact_payload, handle, ensure_ascii=False, separators=(",", ":"))
    _replace_generated_file(artifact_tmp, paths.default_artifact)

    model_payload = _build_linear_ranker_model(dataset_version, generated_at, edges)
    model_tmp = paths.default_model.with_suffix(paths.default_model.suffix + ".tmp")
    with model_tmp.open("w", encoding="utf-8") as handle:
        json.dump(model_payload, handle, ensure_ascii=False, indent=2)
    _replace_generated_file(model_tmp, paths.default_model)

    _record_training_build(
        dataset_version=dataset_version,
        model_version=model_payload["version"],
        status="completed",
        artifact_path=paths.default_artifact,
        model_path=paths.default_model,
        source_rows=stats.csv_rows,
        accepted_rows=accepted_rows,
        rejected_rows=rejected_rows,
        edge_count=len(edges),
    )

    return RouteTrainingBuildResult(
        dataset_version=dataset_version,
        model_version=model_payload["version"],
        source_rows=stats.csv_rows,
        accepted_rows=accepted_rows,
        rejected_rows=rejected_rows,
        edge_count=len(edges),
        artifact_path=paths.default_artifact,
        model_path=paths.default_model,
    )


def normalize_vehicle_code(raw_code: object) -> str:
    value = "" if raw_code is None else str(raw_code).strip()
    if not value or value.lower() in {"na", "nan", "none", "null"}:
        return "ERR-ERR"
    compact = re.sub(r"[\s_\-]+", "", value.upper())
    match = re.match(r"^([A-Z]+)?(\d+)?", compact)
    if not match:
        return "ERR-ERR"
    prefix = match.group(1) or "ERR"
    number = match.group(2) or "ERR"
    if prefix == "ERR" and number == "ERR":
        return "ERR-ERR"
    return f"{prefix}-{number}"


def _normalize_ticket_row(row: dict[str, str], stats: RouteTrainingStats | None = None) -> dict[str, str | float | int | None]:
    def pick(*names: str, required: bool = True, default: str = "") -> str:
        for name in names:
            value = row.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        if required:
            raise ValueError("missing required field")
        return default

    transport_type = _normalize_transport_type(pick("transport_type", "type", required=False))
    if not transport_type:
        raise ValueError("unsupported transport type")

    price = _parse_optional_price(pick("price", required=False))
    if price is None and stats:
        stats.missing_price_count += 1
    duration = _parse_optional_duration(pick("duration_minutes", required=False))
    if duration is None:
        duration = _duration_between(
            pick("departure_time", "depart_time", required=False),
            pick("arrival_time", "arrive_time", required=False),
        )
    if duration is None and stats:
        stats.missing_duration_count += 1

    from_city_en, from_city_name = _split_bilingual_name(pick("from_city", "departure_city", required=False))
    to_city_en, to_city_name = _split_bilingual_name(pick("to_city", "arrival_city", required=False))
    from_city_code = pick("from_city_code", required=False, default=_stable_code(from_city_en or from_city_name))
    to_city_code = pick("to_city_code", required=False, default=_stable_code(to_city_en or to_city_name))
    if not from_city_code or not to_city_code:
        raise ValueError("missing city")

    from_station = pick("from_station", "from_station_code", "departure", required=False)
    to_station = pick("to_station", "to_station_code", "arrival", required=False)
    if not from_station or not to_station:
        raise ValueError("missing station")
    from_station_en, from_station_name = _split_bilingual_name(
        pick("from_station_name", "departure_name", required=False, default=from_station)
    )
    to_station_en, to_station_name = _split_bilingual_name(
        pick("to_station_name", "arrival_name", required=False, default=to_station)
    )
    data_source = pick("provider", "platform", required=False, default="historical_csv")
    normalized_code = normalize_vehicle_code(pick("flight_train_no", "train_no_or_flight_no", "code", required=False))
    if stats:
        stats.normalized_code_count += 1
        if "ERR" in normalized_code:
            stats.err_code_count += 1
            if stats.code_error_counts is not None:
                stats.code_error_counts[data_source] = stats.code_error_counts.get(data_source, 0) + 1

    return {
        "from_city_code": from_city_code,
        "to_city_code": to_city_code,
        "from_city": from_city_name or from_city_en or from_city_code,
        "to_city": to_city_name or to_city_en or to_city_code,
        "from_city_en": pick("from_city_en", required=False, default=from_city_en or from_city_code),
        "to_city_en": pick("to_city_en", required=False, default=to_city_en or to_city_code),
        "from_station": from_station,
        "to_station": to_station,
        "from_station_name": from_station_name or from_station_en or from_station,
        "to_station_name": to_station_name or to_station_en or to_station,
        "from_station_en": pick("from_station_en", required=False, default=from_station_en or ""),
        "to_station_en": pick("to_station_en", required=False, default=to_station_en or ""),
        "transport_type": transport_type,
        "departure_date": _compose_departure_date(
            pick("departure_date", required=False),
            pick("year", required=False),
            pick("date", required=False),
        ),
        "departure_time": pick("departure_time", "depart_time", required=False, default=""),
        "flight_train_no": normalized_code,
        "price": price,
        "duration_minutes": duration,
        "data_source": data_source,
    }


def _process_train_line_workbook(
    *,
    xlsx_file: Path,
    station_city_map: dict[str, dict],
    cities: dict[str, dict],
    stations: dict[str, dict],
    buckets: dict[tuple[str, str, str], dict],
    stats: RouteTrainingStats,
) -> None:
    grouped: dict[str, list[dict]] = {}
    rows = _xlsx_sheet_rows(xlsx_file, "TrainDetails")
    try:
        header = next(rows)
    except StopIteration:
        return
    header_index = {str(value).strip(): index for index, value in enumerate(header) if str(value).strip()}
    code_col = _first_existing(header_index, "车次", "TrainCode")
    station_col = _first_existing(header_index, "站点名称", "TrainStation")
    if code_col is None or station_col is None:
        return
    id_col = _first_existing(header_index, "ID")
    arrive_col = _first_existing(header_index, "到达时间")
    depart_col = _first_existing(header_index, "出发时间")
    elapsed_col = _first_existing(header_index, "历时（min）", "历时(min)", "历时")
    mileage_col = _first_existing(header_index, "里程（km）", "里程(km)", "里程")

    for row in rows:
        stats.excel_stop_rows += 1
        raw_code = _row_value(row, code_col)
        station_name = _clean_value(_row_value(row, station_col))
        if not raw_code or not station_name:
            continue
        code = normalize_vehicle_code(raw_code)
        if "ERR" in code:
            stats.err_code_count += 1
            if stats.code_error_counts is not None:
                key = f"line_template:{xlsx_file.name}"
                stats.code_error_counts[key] = stats.code_error_counts.get(key, 0) + 1
        stats.normalized_code_count += 1
        grouped.setdefault(code, []).append(
            {
                "id": _parse_float(_row_value(row, id_col)) if id_col is not None else len(grouped.get(code, [])),
                "code": code,
                "station_name": station_name,
                "arrival": _row_value(row, arrive_col),
                "departure": _row_value(row, depart_col),
                "elapsed": _parse_optional_duration(_row_value(row, elapsed_col)) if elapsed_col is not None else None,
                "mileage": _parse_float(_row_value(row, mileage_col)) if mileage_col is not None else None,
            }
        )

    for code, stops in grouped.items():
        if len(stops) < 2:
            continue
        stats.excel_train_count += 1
        stops.sort(key=lambda item: item["id"] if item["id"] is not None else 0)
        enriched: list[dict] = []
        for stop in stops:
            mapping = station_city_map.get(_station_key(stop["station_name"]))
            if mapping is None:
                stats.unmapped_station_count += 1
                if stats.unmapped_station_counts is not None:
                    station_key = str(stop["station_name"])
                    stats.unmapped_station_counts[station_key] = stats.unmapped_station_counts.get(station_key, 0) + 1
            enriched.append({**stop, "mapping": mapping})
        for start_index in range(len(enriched) - 1):
            for end_index in range(start_index + 1, len(enriched)):
                stats.excel_expanded_segments += 1
                start = enriched[start_index]
                end = enriched[end_index]
                from_mapping = start["mapping"]
                to_mapping = end["mapping"]
                if not from_mapping or not to_mapping or from_mapping["city_code"] == to_mapping["city_code"]:
                    stats.excel_rejected_segments += 1
                    continue
                duration = _line_segment_duration(start, end)
                if duration is None or duration <= 0 or duration > MAX_REASONABLE_SEGMENT_MINUTES:
                    stats.excel_rejected_segments += 1
                    continue
                _register_line_template_city(cities, from_mapping)
                _register_line_template_city(cities, to_mapping)
                from_station_code = _line_station_code(start["station_name"])
                to_station_code = _line_station_code(end["station_name"])
                stations.setdefault(
                    from_station_code,
                    {
                        "code": from_station_code,
                        "name": start["station_name"],
                        "name_en": from_mapping.get("station_name_en") or start["station_name"],
                        "city_code": from_mapping["city_code"],
                        "station_type": "train_station",
                    },
                )
                stations.setdefault(
                    to_station_code,
                    {
                        "code": to_station_code,
                        "name": end["station_name"],
                        "name_en": to_mapping.get("station_name_en") or end["station_name"],
                        "city_code": to_mapping["city_code"],
                        "station_type": "train_station",
                    },
                )
                _add_edge_sample(
                    buckets,
                    from_mapping["city_code"],
                    to_mapping["city_code"],
                    "train",
                    price=None,
                    duration_minutes=duration,
                    data_source=f"line_template:{xlsx_file.name}",
                    is_template=True,
                )
                stats.excel_accepted_segments += 1
                stats.missing_price_count += 1


def _build_edge(from_city_code: str, to_city_code: str, transport_type: str, bucket: dict) -> dict:
    prices = [float(value) for value in bucket["prices"]]
    durations = [int(value) for value in bucket["durations"]]
    sample_count = int(bucket.get("sample_count", 0))
    estimated_duration = int(round(float(median(durations)))) if durations else _fallback_duration(transport_type)
    estimated_price = round(float(median(prices)), 2) if prices else _fallback_price(transport_type, estimated_duration)
    service_score = min(1.0, sample_count / 365.0)
    availability_score = min(1.0, sample_count / 120.0)
    evidence_score = min(0.35, sample_count * 0.0025)
    price_penalty = 0.0 if prices else 0.18
    duration_penalty = 0.0 if durations else 0.14
    template_penalty = 0.08 if bucket.get("template_count", 0) and not bucket.get("csv_count", 0) else 0.0
    confidence = min(0.99, max(0.18, 0.45 + evidence_score - price_penalty - duration_penalty - template_penalty))
    return {
        "from_city_code": from_city_code,
        "to_city_code": to_city_code,
        "transport_type": transport_type,
        "sample_count": sample_count,
        "estimated_price": estimated_price,
        "estimated_duration_minutes": estimated_duration,
        "service_frequency_score": round(service_score, 4),
        "availability_score": round(availability_score, 4),
        "confidence": round(confidence, 4),
        "price_stability_score": _stability(prices) if prices else 0.35,
        "duration_stability_score": _stability(durations) if durations else 0.35,
        "data_source": ",".join(sorted(bucket["sources"])) or "historical_csv",
    }


def _add_edge_sample(
    buckets: dict[tuple[str, str, str], dict],
    from_city_code: str,
    to_city_code: str,
    transport_type: str,
    *,
    price: object,
    duration_minutes: object,
    data_source: str,
    is_template: bool,
) -> None:
    if from_city_code == to_city_code:
        return
    bucket = buckets.setdefault(
        (from_city_code, to_city_code, transport_type),
        {
            "prices": [],
            "durations": [],
            "sources": set(),
            "sample_count": 0,
            "csv_count": 0,
            "template_count": 0,
        },
    )
    parsed_price = _parse_optional_price(price)
    parsed_duration = _parse_optional_duration(duration_minutes)
    if parsed_price is not None:
        bucket["prices"].append(parsed_price)
    if parsed_duration is not None:
        bucket["durations"].append(parsed_duration)
    bucket["sources"].add(data_source)
    bucket["sample_count"] += 1
    if is_template:
        bucket["template_count"] += 1
    else:
        bucket["csv_count"] += 1


def _normalize_transport_type(raw_value: str) -> str:
    value = _clean_value(raw_value).lower()
    if value in {"rail", "train", "火车", "高铁", "动车"}:
        return "train"
    if value in {"flight", "air", "plane", "航班", "飞机"}:
        return "flight"
    return ""


def _parse_optional_price(value: object) -> float | None:
    parsed = _parse_float(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _parse_optional_duration(value: object) -> int | None:
    parsed = _parse_float(value)
    if parsed is None or parsed <= 0:
        return None
    return int(round(parsed))


def _duration_between(start: object, end: object) -> int | None:
    start_minutes = _parse_time_minutes(start)
    end_minutes = _parse_time_minutes(end)
    if start_minutes is None or end_minutes is None:
        return None
    duration = end_minutes - start_minutes
    while duration <= 0:
        duration += 24 * 60
    if duration > MAX_REASONABLE_SEGMENT_MINUTES:
        return None
    return duration


def _line_segment_duration(start: dict, end: dict) -> int | None:
    start_elapsed = start.get("elapsed")
    end_elapsed = end.get("elapsed")
    if isinstance(start_elapsed, int) and isinstance(end_elapsed, int) and end_elapsed > start_elapsed:
        return end_elapsed - start_elapsed
    return _duration_between(start.get("departure"), end.get("arrival"))


def _parse_time_minutes(value: object) -> int | None:
    cleaned = _clean_value(value)
    if not cleaned:
        return None
    if re.match(r"^\d+(\.\d+)?$", cleaned):
        numeric = float(cleaned)
        fraction = numeric % 1
        if fraction == 0 and numeric <= 24:
            return int(round(numeric * 60))
        return int(round(fraction * 24 * 60))
    match = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?$", cleaned)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if minute >= 60:
        return None
    return hour * 60 + minute


def _parse_float(value: object) -> float | None:
    cleaned = _clean_value(value)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _compose_departure_date(existing: str, year: str, month_day: str) -> str:
    existing = _clean_value(existing)
    if existing:
        return existing
    year = _clean_value(year)
    month_day = _clean_value(month_day)
    if not year or year.lower() == "na" or not month_day or month_day.lower() == "na":
        return "historical"
    return f"{year}-{month_day}"


def _split_bilingual_name(value: str) -> tuple[str, str]:
    cleaned = _clean_value(value)
    if not cleaned:
        return "", ""
    if " - " in cleaned:
        left, right = cleaned.split(" - ", 1)
        return left.strip(), _compact_cjk_spaces(right.strip())
    if re.fullmatch(r"[A-Za-z0-9\s.'()-]+", cleaned):
        return cleaned, ""
    return "", _compact_cjk_spaces(cleaned)


def _stable_code(value: str) -> str:
    cleaned = _clean_value(value)
    if not cleaned:
        return ""
    ascii_code = re.sub(r"[^A-Za-z0-9]+", "", cleaned).upper()
    if ascii_code:
        return ascii_code
    return re.sub(r"\s+", "", cleaned)


def _clean_value(value: object) -> str:
    if value is None:
        return ""
    cleaned = str(value).strip()
    if cleaned.lower() in {"na", "nan", "none", "null"}:
        return ""
    return cleaned


def _compact_cjk_spaces(value: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", value):
        return re.sub(r"\s+", "", value)
    return value


def _register_city_pair(cities: dict[str, dict], normalized: dict) -> None:
    _register_city(
        cities,
        str(normalized["from_city_code"]),
        str(normalized["from_city"]),
        str(normalized["from_city_en"]),
    )
    _register_city(
        cities,
        str(normalized["to_city_code"]),
        str(normalized["to_city"]),
        str(normalized["to_city_en"]),
    )


def _register_city(cities: dict[str, dict], code: str, name: str, name_en: str) -> None:
    if not code:
        return
    cities.setdefault(
        code,
        {
            "code": code,
            "name": name or code,
            "name_en": name_en or name or code,
            "country": "China",
        },
    )


def _register_line_template_city(cities: dict[str, dict], mapping: dict) -> None:
    _register_city(
        cities,
        mapping["city_code"],
        mapping.get("city_name") or mapping["city_code"],
        mapping.get("city_name_en") or mapping["city_code"],
    )


def _register_station_pair(stations: dict[str, dict], normalized: dict) -> None:
    transport_type = str(normalized["transport_type"])
    stations.setdefault(
        str(normalized["from_station"]),
        {
            "code": str(normalized["from_station"]),
            "name": str(normalized["from_station_name"]),
            "name_en": str(normalized["from_station_en"] or normalized["from_station_name"]),
            "city_code": str(normalized["from_city_code"]),
            "station_type": _station_type(transport_type),
        },
    )
    stations.setdefault(
        str(normalized["to_station"]),
        {
            "code": str(normalized["to_station"]),
            "name": str(normalized["to_station_name"]),
            "name_en": str(normalized["to_station_en"] or normalized["to_station_name"]),
            "city_code": str(normalized["to_city_code"]),
            "station_type": _station_type(transport_type),
        },
    )


def _record_station_mapping(votes: dict[str, dict[str, dict]], normalized: dict, side: str) -> None:
    station_name = str(normalized[f"{side}_station_name"])
    key = _station_key(station_name)
    if not key:
        return
    city_code = str(normalized[f"{side}_city_code"])
    city_map = votes.setdefault(key, {})
    vote = city_map.setdefault(
        city_code,
        {
            "count": 0,
            "city_code": city_code,
            "city_name": str(normalized[f"{side}_city"]),
            "city_name_en": str(normalized[f"{side}_city_en"]),
            "station_name": station_name,
            "station_name_en": str(normalized.get(f"{side}_station_en") or station_name),
        },
    )
    vote["count"] += 1


def _finalize_station_city_map(votes: dict[str, dict[str, dict]], stats: RouteTrainingStats) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for station_key, city_votes in votes.items():
        if len(city_votes) > 1:
            stats.station_mapping_conflicts += 1
            if stats.station_mapping_conflict_examples is not None and len(stats.station_mapping_conflict_examples) < 20:
                stats.station_mapping_conflict_examples.append(
                    {
                        "station": station_key,
                        "candidates": sorted(
                            [
                                {
                                    "city_code": item["city_code"],
                                    "city_name": item["city_name"],
                                    "count": item["count"],
                                }
                                for item in city_votes.values()
                            ],
                            key=lambda item: (-int(item["count"]), str(item["city_code"])),
                        ),
                    }
                )
        best = max(city_votes.values(), key=lambda item: int(item["count"]))
        result[station_key] = best
    return result


def _station_key(value: str) -> str:
    return re.sub(r"\s+", "", _clean_value(value)).lower()


def _line_station_code(station_name: str) -> str:
    return "LINE_" + _stable_code(station_name)


def _fallback_duration(transport_type: str) -> int:
    return 120 if transport_type == "flight" else 240


def _fallback_price(transport_type: str, duration_minutes: int) -> float:
    if transport_type == "flight":
        return round(max(300.0, duration_minutes * 2.2), 2)
    return round(max(20.0, duration_minutes * 0.35), 2)


def _canonicalize_city_graph(
    cities: dict[str, dict],
    stations: dict[str, dict],
    buckets: dict[tuple[str, str, str], dict],
    stats: RouteTrainingStats,
) -> None:
    usage: dict[str, int] = {code: 0 for code in cities}
    for (from_code, to_code, _), bucket in buckets.items():
        sample_count = int(bucket.get("sample_count", 0))
        usage[from_code] = usage.get(from_code, 0) + sample_count
        usage[to_code] = usage.get(to_code, 0) + sample_count
    for station in stations.values():
        city_code = station.get("city_code")
        if city_code:
            usage[city_code] = usage.get(city_code, 0) + 1

    groups: dict[str, list[str]] = {}
    for code, city in cities.items():
        key = _city_alias_key(city)
        if key:
            groups.setdefault(key, []).append(code)

    alias: dict[str, str] = {}
    for key, codes in groups.items():
        candidate_groups = _safe_city_alias_groups(key, codes, cities)
        for candidate_codes in candidate_groups:
            if len(candidate_codes) <= 1:
                continue
            canonical = max(candidate_codes, key=lambda code: (usage.get(code, 0), -len(code), code))
            for code in candidate_codes:
                if code != canonical:
                    alias[code] = canonical
            stats.alias_merged_city_count += len(candidate_codes) - 1
            if stats.city_alias_merge_examples is not None and len(stats.city_alias_merge_examples) < 20:
                stats.city_alias_merge_examples.append(
                    {
                        "alias_key": key,
                        "canonical": canonical,
                        "merged": sorted(code for code in candidate_codes if code != canonical),
                    }
                )
    _apply_city_aliases(cities, stations, buckets, stats, alias)


def _safe_city_alias_groups(key: str, codes: list[str], cities: dict[str, dict]) -> list[list[str]]:
    if len(codes) <= 1:
        return [codes]
    if not key.startswith("zh:"):
        return [codes]
    groups: list[list[str]] = []
    for code in codes:
        token = _city_latin_token(cities[code])
        placed = False
        for group in groups:
            representative = _city_latin_token(cities[group[0]])
            if _latin_alias_close(token, representative):
                group.append(code)
                placed = True
                break
        if not placed:
            groups.append([code])
    return groups


def _city_latin_token(city: dict) -> str:
    raw = str(city.get("name_en") or city.get("code") or "")
    token = re.sub(r"[^a-z0-9]+", "", raw.lower())
    return token or re.sub(r"[^a-z0-9]+", "", str(city.get("code") or "").lower())


def _latin_alias_close(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    if left in right or right in left:
        return min(len(left), len(right)) >= 4
    return _levenshtein_distance(left, right) <= 2


def _levenshtein_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[j - 1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (0 if left_char == right_char else 1),
                )
            )
        previous = current
    return previous[-1]


def _apply_city_aliases(
    cities: dict[str, dict],
    stations: dict[str, dict],
    buckets: dict[tuple[str, str, str], dict],
    stats: RouteTrainingStats,
    alias: dict[str, str],
) -> None:
    if not alias:
        return

    merged_buckets: dict[tuple[str, str, str], dict] = {}
    for (from_code, to_code, transport_type), bucket in buckets.items():
        new_from = alias.get(from_code, from_code)
        new_to = alias.get(to_code, to_code)
        if new_from == new_to:
            stats.alias_self_loop_dropped_count += int(bucket.get("sample_count", 0))
            continue
        target = merged_buckets.setdefault(
            (new_from, new_to, transport_type),
            {
                "prices": [],
                "durations": [],
                "sources": set(),
                "sample_count": 0,
                "csv_count": 0,
                "template_count": 0,
            },
        )
        target["prices"].extend(bucket.get("prices", []))
        target["durations"].extend(bucket.get("durations", []))
        target["sources"].update(bucket.get("sources", set()))
        target["sample_count"] += int(bucket.get("sample_count", 0))
        target["csv_count"] += int(bucket.get("csv_count", 0))
        target["template_count"] += int(bucket.get("template_count", 0))
    buckets.clear()
    buckets.update(merged_buckets)

    for station in stations.values():
        city_code = station.get("city_code")
        if city_code in alias:
            station["city_code"] = alias[city_code]
    for code in list(cities.keys()):
        if code in alias:
            del cities[code]


def _city_alias_key(city: dict) -> str:
    name = _compact_cjk_spaces(str(city.get("name") or ""))
    if re.search(r"[\u4e00-\u9fff]", name):
        return "zh:" + name
    name_en = str(city.get("name_en") or name or city.get("code") or "")
    normalized = re.sub(r"[^a-z0-9]+", "", name_en.lower())
    return "en:" + normalized if normalized else ""


def _record_edge_quality_stats(edges: list[dict], stats: RouteTrainingStats) -> None:
    for edge in edges:
        if edge["transport_type"] == "train":
            stats.train_edge_count += 1
        elif edge["transport_type"] == "flight":
            stats.flight_edge_count += 1
        if float(edge.get("confidence", 0)) < 0.35:
            stats.low_confidence_edge_count += 1
        data_source = str(edge.get("data_source", ""))
        if "line_template:" in data_source and "," not in data_source and "12306" not in data_source:
            stats.template_only_edge_count += 1


def _stats_payload(stats: RouteTrainingStats) -> dict:
    return {
        "source_csv_files": stats.csv_files,
        "source_xlsx_files": stats.xlsx_files,
        "csv_rows": stats.csv_rows,
        "csv_accepted_rows": stats.csv_accepted_rows,
        "csv_rejected_rows": stats.csv_rejected_rows,
        "excel_train_count": stats.excel_train_count,
        "excel_stop_rows": stats.excel_stop_rows,
        "excel_expanded_segments": stats.excel_expanded_segments,
        "excel_accepted_segments": stats.excel_accepted_segments,
        "excel_rejected_segments": stats.excel_rejected_segments,
        "unmapped_station_count": stats.unmapped_station_count,
        "station_mapping_conflicts": stats.station_mapping_conflicts,
        "missing_price_count": stats.missing_price_count,
        "missing_duration_count": stats.missing_duration_count,
        "normalized_code_count": stats.normalized_code_count,
        "err_code_count": stats.err_code_count,
        "template_only_edge_count": stats.template_only_edge_count,
        "train_edge_count": stats.train_edge_count,
        "flight_edge_count": stats.flight_edge_count,
        "low_confidence_edge_count": stats.low_confidence_edge_count,
        "alias_merged_city_count": stats.alias_merged_city_count,
        "alias_self_loop_dropped_count": stats.alias_self_loop_dropped_count,
        "top_unmapped_stations": _top_counts(stats.unmapped_station_counts or {}),
        "code_error_sources": _top_counts(stats.code_error_counts or {}),
        "station_mapping_conflict_examples": stats.station_mapping_conflict_examples or [],
        "city_alias_merge_examples": stats.city_alias_merge_examples or [],
    }


def _top_counts(values: dict[str, int], limit: int = 20) -> list[dict]:
    return [
        {"value": key, "count": count}
        for key, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _xlsx_sheet_rows(path: Path, sheet_name: str) -> Iterable[list[str]]:
    with zipfile.ZipFile(path) as workbook:
        shared_strings = _xlsx_shared_strings(workbook)
        sheet_path = _xlsx_sheet_path(workbook, sheet_name)
        if not sheet_path:
            return
        with workbook.open(sheet_path) as sheet_file:
            for _, row_element in ET.iterparse(sheet_file, events=("end",)):
                if not row_element.tag.endswith("row"):
                    continue
                values: list[str] = []
                for cell in row_element:
                    if not cell.tag.endswith("c"):
                        continue
                    ref = cell.attrib.get("r", "")
                    col_index = _xlsx_col_index(ref)
                    while len(values) <= col_index:
                        values.append("")
                    values[col_index] = _xlsx_cell_value(cell, shared_strings)
                row_element.clear()
                yield values


def _xlsx_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.iter():
        if item.tag.endswith("si"):
            texts = [node.text or "" for node in item.iter() if node.tag.endswith("t")]
            values.append("".join(texts))
    return values


def _xlsx_sheet_path(workbook: zipfile.ZipFile, sheet_name: str) -> str:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    rels = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels_root
        if "Id" in rel.attrib and "Target" in rel.attrib
    }
    for sheet in workbook_root.iter():
        if not sheet.tag.endswith("sheet") or sheet.attrib.get("name") != sheet_name:
            continue
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rels.get(rel_id or "")
        if not target:
            return ""
        normalized_target = target.lstrip("/")
        return normalized_target if normalized_target.startswith("xl/") else "xl/" + normalized_target
    return ""


def _xlsx_col_index(ref: str) -> int:
    letters = re.match(r"([A-Z]+)", ref or "")
    if not letters:
        return 0
    index = 0
    for char in letters.group(1):
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        texts = [node.text or "" for node in cell.iter() if node.tag.endswith("t")]
        return "".join(texts)
    value_node = next((node for node in cell if node.tag.endswith("v")), None)
    value = value_node.text if value_node is not None else ""
    if cell_type == "s" and value:
        index = int(value)
        return shared_strings[index] if 0 <= index < len(shared_strings) else ""
    return value or ""


def _first_existing(header_index: dict[str, int], *names: str) -> int | None:
    for name in names:
        if name in header_index:
            return header_index[name]
    return None


def _row_value(row: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(row):
        return ""
    return row[index]


def _stability(values: Iterable[float | int]) -> float:
    values = [float(value) for value in values]
    if len(values) <= 1:
        return 1.0
    mean = sum(values) / len(values)
    if mean <= 0:
        return 0.0
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return round(max(0.0, 1.0 - (variance ** 0.5 / mean)), 4)


def _station_type(transport_type: str) -> str:
    return "airport" if transport_type == "flight" else "train_station"


def _build_linear_ranker_model(dataset_version: str, generated_at: str, edges: list[dict]) -> dict:
    edge_count = max(len(edges), 1)
    average_confidence = sum(float(edge["confidence"]) for edge in edges) / edge_count if edges else 0.0
    stability = (
        sum((float(edge["price_stability_score"]) + float(edge["duration_stability_score"])) / 2 for edge in edges)
        / edge_count
        if edges
        else 0.0
    )
    stability_weight = 0.10 if stability >= 0.75 else 0.14
    confidence_weight = 0.12 if average_confidence >= 0.75 else 0.16
    return {
        "version": "linear_ranker_v1_" + generated_at.replace(":", "").replace("-", ""),
        "dataset_version": dataset_version,
        "generated_at": generated_at,
        "model_type": "linear_ranker",
        "weights": {
            "price_weight": 0.35,
            "duration_weight": 0.25,
            "transfer_weight": 0.20,
            "service_weight": 0.15,
            "confidence_weight": confidence_weight,
            "stability_weight": stability_weight,
            "sample_count_weight": 0.04,
            "required_transfer_bonus": 0.08,
            "direct_guard_penalty": 0.40,
            "transport_mix_penalty": 0.03,
        },
    }


def _record_training_build(
    *,
    dataset_version: str,
    model_version: str,
    status: str,
    artifact_path: Path,
    model_path: Path,
    source_rows: int,
    accepted_rows: int,
    rejected_rows: int,
    edge_count: int,
) -> None:
    try:
        import mysql.connector
    except ImportError:
        return
    parsed = urlparse(settings.database_url)
    database = parsed.path.lstrip("/")
    if not database:
        return
    try:
        connection = mysql.connector.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=unquote(parsed.username or "root"),
            password=unquote(parsed.password or ""),
            database=database,
            charset="utf8mb4",
            collation="utf8mb4_general_ci",
            use_unicode=True,
        )
    except mysql.connector.Error:
        return
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS route_training_builds (
                dataset_version VARCHAR(120) PRIMARY KEY,
                model_version VARCHAR(120) NOT NULL,
                status VARCHAR(40) NOT NULL,
                artifact_path VARCHAR(500) NOT NULL,
                model_path VARCHAR(500) NOT NULL,
                source_rows INT NOT NULL DEFAULT 0,
                accepted_rows INT NOT NULL DEFAULT 0,
                rejected_rows INT NOT NULL DEFAULT 0,
                edge_count INT NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_route_training_model (model_version)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        cursor.execute(
            """
            INSERT INTO route_training_builds (
                dataset_version, model_version, status, artifact_path, model_path,
                source_rows, accepted_rows, rejected_rows, edge_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                model_version = VALUES(model_version),
                status = VALUES(status),
                artifact_path = VALUES(artifact_path),
                model_path = VALUES(model_path),
                source_rows = VALUES(source_rows),
                accepted_rows = VALUES(accepted_rows),
                rejected_rows = VALUES(rejected_rows),
                edge_count = VALUES(edge_count)
            """,
            (
                dataset_version,
                model_version,
                status,
                str(artifact_path),
                str(model_path),
                source_rows,
                accepted_rows,
                rejected_rows,
                edge_count,
            ),
        )
        connection.commit()
    finally:
        connection.close()
