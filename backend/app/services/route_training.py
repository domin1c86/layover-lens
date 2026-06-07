from __future__ import annotations

import csv
import gzip
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Iterable
from urllib.parse import unquote, urlparse

from app.config import settings
from app.data_source.base import CatalogSnapshot, CityRecord, SegmentEdgeRecord, StationRecord

ARTIFACT_SCHEMA_VERSION = 1
DEFAULT_MODEL_VERSION = "builtin_default"
DEFAULT_MODEL_FILENAME = "linear_ranker_v1.json"
DEFAULT_ARTIFACT_FILENAME = "route_edges_v1.json.gz"


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
    mode = settings.route_dataset_mode.lower()
    if mode not in {"auto", "mock", "historical"}:
        mode = "auto"

    has_artifact = paths.default_artifact.exists()
    has_model = paths.default_model.exists()
    if mode == "mock" or (mode == "auto" and not csv_files and not has_artifact):
        return RouteDatasetSelection(
            mode="mock",
            has_csv=bool(csv_files),
            artifact_path=None,
            model_path=None,
            dataset_version="mock",
            model_version=DEFAULT_MODEL_VERSION,
        )

    if not has_artifact:
        return RouteDatasetSelection(
            mode="mock",
            has_csv=bool(csv_files),
            artifact_path=None,
            model_path=None,
            dataset_version="mock",
            model_version=DEFAULT_MODEL_VERSION,
            warning="route_training_csv_present_without_artifact",
        )

    metadata = read_artifact_metadata(paths.default_artifact)
    model_version = DEFAULT_MODEL_VERSION
    if has_model:
        model_version = read_model_version(paths.default_model)
    return RouteDatasetSelection(
        mode="historical",
        has_csv=bool(csv_files),
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
    }


def read_model_version(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return str(payload.get("version") or DEFAULT_MODEL_VERSION)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_MODEL_VERSION


def load_historical_catalog(path: Path) -> CatalogSnapshot:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    cities = tuple(
        CityRecord(
            code=item["code"],
            name=item.get("name") or item["code"],
            name_en=item.get("name_en") or item.get("name") or item["code"],
            country=item.get("country", "中国"),
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


def build_route_training_artifacts() -> RouteTrainingBuildResult:
    paths = ensure_route_training_dirs()
    csv_files = sorted(paths.raw_csv.glob("*.csv"))
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    dataset_version = "historical_" + generated_at.replace(":", "").replace("-", "")

    cities: dict[str, dict] = {}
    stations: dict[str, dict] = {}
    buckets: dict[tuple[str, str, str], dict[str, list[float] | list[int] | set[str]]] = {}
    seen: set[tuple[str, str, str, str, str, str]] = set()
    source_rows = 0
    accepted_rows = 0
    rejected_rows = 0

    for csv_file in csv_files:
        with csv_file.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                source_rows += 1
                try:
                    normalized = _normalize_ticket_row(row)
                except ValueError:
                    rejected_rows += 1
                    continue
                signature = (
                    normalized["from_station"],
                    normalized["to_station"],
                    normalized["transport_type"],
                    normalized["departure_date"],
                    normalized["departure_time"],
                    normalized["flight_train_no"],
                )
                if signature in seen:
                    continue
                seen.add(signature)
                accepted_rows += 1
                cities.setdefault(
                    normalized["from_city_code"],
                    {
                        "code": normalized["from_city_code"],
                        "name": normalized["from_city"],
                        "name_en": normalized["from_city_en"],
                        "country": "中国",
                    },
                )
                cities.setdefault(
                    normalized["to_city_code"],
                    {
                        "code": normalized["to_city_code"],
                        "name": normalized["to_city"],
                        "name_en": normalized["to_city_en"],
                        "country": "中国",
                    },
                )
                stations.setdefault(
                    normalized["from_station"],
                    {
                        "code": normalized["from_station"],
                        "name": normalized["from_station_name"],
                        "name_en": normalized["from_station_en"],
                        "city_code": normalized["from_city_code"],
                        "station_type": _station_type(normalized["transport_type"]),
                    },
                )
                stations.setdefault(
                    normalized["to_station"],
                    {
                        "code": normalized["to_station"],
                        "name": normalized["to_station_name"],
                        "name_en": normalized["to_station_en"],
                        "city_code": normalized["to_city_code"],
                        "station_type": _station_type(normalized["transport_type"]),
                    },
                )
                bucket = buckets.setdefault(
                    (
                        normalized["from_city_code"],
                        normalized["to_city_code"],
                        normalized["transport_type"],
                    ),
                    {"prices": [], "durations": [], "sources": set()},
                )
                bucket["prices"].append(float(normalized["price"]))  # type: ignore[union-attr]
                bucket["durations"].append(int(normalized["duration_minutes"]))  # type: ignore[union-attr]
                bucket["sources"].add(normalized["data_source"])  # type: ignore[union-attr]

    edges = [
        _build_edge(from_city_code, to_city_code, transport_type, bucket)
        for (from_city_code, to_city_code, transport_type), bucket in sorted(buckets.items())
    ]
    artifact_payload = {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "dataset_version": dataset_version,
        "generated_at": generated_at,
        "source_files": [file.name for file in csv_files],
        "source_rows": source_rows,
        "accepted_rows": accepted_rows,
        "rejected_rows": rejected_rows,
        "cities": sorted(cities.values(), key=lambda item: item["code"]),
        "stations": sorted(stations.values(), key=lambda item: item["code"]),
        "edges": edges,
    }
    with gzip.open(paths.default_artifact, "wt", encoding="utf-8") as handle:
        json.dump(artifact_payload, handle, ensure_ascii=False, separators=(",", ":"))

    model_payload = _build_linear_ranker_model(dataset_version, generated_at, edges)
    with paths.default_model.open("w", encoding="utf-8") as handle:
        json.dump(model_payload, handle, ensure_ascii=False, indent=2)

    _record_training_build(
        dataset_version=dataset_version,
        model_version=model_payload["version"],
        status="completed",
        artifact_path=paths.default_artifact,
        model_path=paths.default_model,
        source_rows=source_rows,
        accepted_rows=accepted_rows,
        rejected_rows=rejected_rows,
        edge_count=len(edges),
    )

    return RouteTrainingBuildResult(
        dataset_version=dataset_version,
        model_version=model_payload["version"],
        source_rows=source_rows,
        accepted_rows=accepted_rows,
        rejected_rows=rejected_rows,
        edge_count=len(edges),
        artifact_path=paths.default_artifact,
        model_path=paths.default_model,
    )


def _normalize_ticket_row(row: dict[str, str]) -> dict[str, str | float | int]:
    def pick(*names: str, required: bool = True, default: str = "") -> str:
        for name in names:
            value = row.get(name)
            if value is not None and value.strip():
                return value.strip()
        if required:
            raise ValueError("missing required field")
        return default

    transport_type = pick("transport_type", "交通方式").lower()
    if transport_type in {"rail", "train", "火车", "高铁", "动车"}:
        transport_type = "train"
    elif transport_type in {"flight", "air", "plane", "航班", "飞机"}:
        transport_type = "flight"
    else:
        raise ValueError("unsupported transport type")

    price = float(pick("price", "票价", "价格"))
    duration = int(float(pick("duration_minutes", "耗时分钟", "耗时")))
    if price < 0 or duration <= 0:
        raise ValueError("invalid price or duration")

    from_city_name = pick("from_city", "出发城市", required=False)
    to_city_name = pick("to_city", "到达城市", required=False)
    from_city_code = pick("from_city_code", "出发城市代码", required=False, default=from_city_name)
    to_city_code = pick("to_city_code", "到达城市代码", required=False, default=to_city_name)
    if not from_city_code or not to_city_code:
        raise ValueError("missing city")
    from_station = pick("from_station", "出发站代码", "from_station_code")
    to_station = pick("to_station", "到达站代码", "to_station_code")
    return {
        "from_city_code": from_city_code,
        "to_city_code": to_city_code,
        "from_city": from_city_name or from_city_code,
        "to_city": to_city_name or to_city_code,
        "from_city_en": pick("from_city_en", default=from_city_code, required=False),
        "to_city_en": pick("to_city_en", default=to_city_code, required=False),
        "from_station": from_station,
        "to_station": to_station,
        "from_station_name": pick("from_station_name", "出发站", required=False, default=from_station),
        "to_station_name": pick("to_station_name", "到达站", required=False, default=to_station),
        "from_station_en": pick("from_station_en", default="", required=False),
        "to_station_en": pick("to_station_en", default="", required=False),
        "transport_type": transport_type,
        "departure_date": pick("departure_date", "出发日期"),
        "departure_time": pick("departure_time", "出发时间"),
        "flight_train_no": pick("flight_train_no", "车次航班号", "train_no_or_flight_no", default="", required=False),
        "price": price,
        "duration_minutes": duration,
        "data_source": pick("provider", "platform", "来源", default="historical_csv", required=False),
    }


def _build_edge(from_city_code: str, to_city_code: str, transport_type: str, bucket: dict) -> dict:
    prices = [float(value) for value in bucket["prices"]]
    durations = [int(value) for value in bucket["durations"]]
    sample_count = len(prices)
    service_score = min(1.0, sample_count / 365.0)
    availability_score = min(1.0, sample_count / 120.0)
    confidence = min(0.99, 0.5 + sample_count * 0.0025)
    return {
        "from_city_code": from_city_code,
        "to_city_code": to_city_code,
        "transport_type": transport_type,
        "sample_count": sample_count,
        "estimated_price": round(float(median(prices)), 2),
        "estimated_duration_minutes": int(round(float(median(durations)))),
        "service_frequency_score": round(service_score, 4),
        "availability_score": round(availability_score, 4),
        "confidence": round(confidence, 4),
        "price_stability_score": _stability(prices),
        "duration_stability_score": _stability(durations),
        "data_source": ",".join(sorted(bucket["sources"])) or "historical_csv",
    }


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
