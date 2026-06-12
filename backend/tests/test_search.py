import gzip
import json
import zipfile
from datetime import date, time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.data_source import reset_data_source_cache
from app.data_source.base import CatalogSnapshot, CityRecord, RouteRecord, StationRecord
from app.main import app
from app.agents.search_agent import CONFIRM_PATTERNS, REJECT_PATTERNS, reset_search_agent_service_cache
from app.services import reset_search_service_cache
from app.services.route_feedback import reset_route_feedback_service_cache
from app.services.route_strategy import RouteStrategyService
from app.services.route_training import (
    build_route_training_artifacts,
    evaluate_route_training_artifact,
    normalize_vehicle_code,
    validate_route_training_artifact,
)
from app.schemas import SearchRequest


@pytest.fixture(autouse=True)
def _use_legacy_agent_model(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_model_provider", "legacy")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "route_dataset_mode", "mock")


def _fresh_client() -> TestClient:
    reset_search_service_cache()
    reset_search_agent_service_cache()
    reset_data_source_cache()
    reset_route_feedback_service_cache()
    return TestClient(app)


def _ai_headers(client: TestClient) -> dict[str, str]:
    email = f"ai-{uuid4().hex[:10]}@example.com"
    client.post("/api/v1/auth/email-verification/send", json={"email": email, "purpose": "register"})
    verification = client.post(
        "/api/v1/auth/email-verification/verify",
        json={"email": email, "purpose": "register", "code": "000000"},
    ).json()
    payload = client.post(
        "/api/v1/auth/register",
        json={
            "username": "ai-tester",
            "email": email,
            "password": "secret123",
            "email_verification_token": verification["verification_token"],
        },
    ).json()
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_health_check() -> None:
    client = _fresh_client()
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_source"].startswith("mock:")
    assert payload["planner_backend"] in {"python", "cpp"}
    assert payload["route_strategy_enabled"] is True
    assert payload["route_strategy_backend"] == "cpp"
    assert payload["segment_provider"] == "mock_graph"
    assert payload["ai_search_backend"]
    assert payload["ai_streaming"] == "reply"
    assert payload["ai_tools_enabled"] is True
    assert payload["ai_token_usage_tracking_enabled"] is True
    assert payload["ai_cached_token_tracking_supported"] is True
    assert payload["ai_poi_enabled"] is True
    assert payload["ai_poi_primary_provider"] == "amap"
    assert payload["ai_poi_dual_verify_enabled"] is False
    assert payload["ai_poi_quota_mode"] == "configured"


def test_ai_chinese_confirm_and_reject_patterns_are_valid() -> None:
    assert any(pattern.match("搜索") for pattern in CONFIRM_PATTERNS)
    assert any(pattern.match("开始搜索") for pattern in CONFIRM_PATTERNS)
    assert any(pattern.match("按这些条件搜索") for pattern in CONFIRM_PATTERNS)
    assert any(pattern.match("取消搜索") for pattern in REJECT_PATTERNS)
    assert any(pattern.match("继续修改") for pattern in REJECT_PATTERNS)


def test_cities_endpoint_returns_seed_data() -> None:
    client = _fresh_client()
    response = client.get("/api/v1/cities")

    assert response.status_code == 200
    payload = response.json()
    assert "cities" in payload
    assert len(payload["cities"]) >= 5
    assert any(city["code"] == "BJ" for city in payload["cities"])


def test_cities_keyword_filter() -> None:
    client = _fresh_client()
    response = client.get("/api/v1/cities", params={"keyword": "北京"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["cities"]) >= 1
    assert all("北京" in city["name"] or city["code"] == "BJ" for city in payload["cities"])


def test_search_endpoint_returns_ranked_routes() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "CD",
            "travel_date": "2026-04-22",
            "optimization_target": "balanced",
            "max_transfers": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] >= 1
    assert payload["total"] == payload["total_count"]
    assert payload["result_mode"] == "strategy"
    assert payload["recommendations"]
    assert payload["routes"] == []
    assert payload["data_mode"] == "mock"
    assert payload["data_notice"]
    assert payload["strategy_notice"]
    assert payload["mock_source_date"]
    first_route = payload["recommendations"][0]
    assert first_route["id"].startswith("strategy_")
    assert first_route["city_path"]
    assert first_route["segments"]
    assert first_route["segments"][0]["recommended_transport_type"] in {"flight", "train"}
    assert first_route["warnings"]


def test_search_endpoint_accepts_legacy_alias_fields() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "北京",
            "to_city": "成都",
            "date": "2026-04-22",
            "optimize": "price",
            "filters": {"max_transfer": 1},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendations"]
    assert all(route["estimated_total_price"] > 0 for route in payload["recommendations"])


def test_search_unknown_city_returns_404() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "Moon",
            "to_city": "CD",
            "travel_date": "2026-04-22",
            "optimization_target": "balanced",
        },
    )

    assert response.status_code == 404


def test_search_rolls_mock_data_to_unseeded_date() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "CD",
            "travel_date": "2026-06-15",
            "optimization_target": "balanced",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] >= 1
    assert payload["data_mode"] == "mock"
    assert payload["mock_source_date"] != "2026-06-15"
    assert payload["result_mode"] == "strategy"
    assert payload["recommendations"][0]["segments"]


def test_search_supports_price_and_transport_filters() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "SH",
            "travel_date": "2026-04-22",
            "optimization_target": "price",
            "preferred_transport_types": ["train"],
            "max_price": 800,
            "max_transfers": 0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] >= 1
    route = payload["recommendations"][0]
    assert route["estimated_total_price"] <= 800
    assert all(segment["recommended_transport_type"] == "train" for segment in route["segments"])


def test_search_supports_transfer_city_constraints() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "CD",
            "travel_date": "2026-04-22",
            "optimization_target": "balanced",
            "required_transfer_cities": ["SH"],
            "excluded_cities": ["WH", "NJ", "XA"],
            "max_transfers": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] >= 1
    for route in payload["recommendations"]:
        transfer_cities = set(route["transfer_cities"])
        assert "上海" in transfer_cities
        assert not (transfer_cities & {"武汉", "南京", "西安"})


def test_search_supports_time_window_filters() -> None:
    client = _fresh_client()
    response = client.post(
        "/api/v1/search",
        json={
            "from_city": "BJ",
            "to_city": "CD",
            "travel_date": "2026-04-22",
            "optimization_target": "balanced",
            "departure_time_range": {"start": "07:30", "end": "08:30"},
            "arrival_time_range": {"start": "10:30", "end": "20:00"},
            "max_transfers": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_count"] >= 1
    assert payload["result_mode"] == "strategy"
    assert payload["recommendations"][0]["segments"]


def _strategy_catalog(include_direct: bool = True) -> CatalogSnapshot:
    cities = (
        CityRecord(code="A", name="Alpha", name_en="Alpha"),
        CityRecord(code="B", name="Beta", name_en="Beta"),
        CityRecord(code="C", name="Gamma", name_en="Gamma"),
    )
    stations = (
        StationRecord(code="AS", name="Alpha Station", city_code="A", station_type="train_station", name_en="Alpha Station"),
        StationRecord(code="BS", name="Beta Station", city_code="B", station_type="train_station", name_en="Beta Station"),
        StationRecord(code="CS", name="Gamma Station", city_code="C", station_type="train_station", name_en="Gamma Station"),
    )
    travel_date = date(2026, 4, 22)
    routes = [
        RouteRecord(
            id="ab",
            from_station="AS",
            to_station="BS",
            transport_type="train",
            departure_date=travel_date,
            departure_time=time(8, 0),
            arrival_date=travel_date,
            arrival_time=time(9, 0),
            price=100,
            duration_minutes=60,
            company="Rail",
            flight_train_no="G1",
            platform="mock",
        ),
        RouteRecord(
            id="bc",
            from_station="BS",
            to_station="CS",
            transport_type="train",
            departure_date=travel_date,
            departure_time=time(10, 0),
            arrival_date=travel_date,
            arrival_time=time(11, 0),
            price=100,
            duration_minutes=60,
            company="Rail",
            flight_train_no="G2",
            platform="mock",
        ),
    ]
    if include_direct:
        routes.append(
            RouteRecord(
                id="ac",
                from_station="AS",
                to_station="CS",
                transport_type="train",
                departure_date=travel_date,
                departure_time=time(8, 0),
                arrival_date=travel_date,
                arrival_time=time(10, 0),
                price=100,
                duration_minutes=120,
                company="Rail",
                flight_train_no="G3",
                platform="mock",
            )
        )
    return CatalogSnapshot(cities=cities, stations=stations, routes=tuple(routes))


def test_strategy_filters_transfer_above_direct_price_guard() -> None:
    service = RouteStrategyService()
    request = SearchRequest(
        from_city="A",
        to_city="C",
        travel_date=date(2026, 4, 22),
        optimization_target="balanced",
        max_transfers=1,
    )

    recommendations = service.recommend(
        request=request,
        catalog=_strategy_catalog(include_direct=True),
        from_city_code="A",
        to_city_code="C",
        source_date=date(2026, 4, 22),
        limit=8,
    )

    assert recommendations
    assert all(item.transfer_count == 0 for item in recommendations)


def test_strategy_cpp_aggregates_segment_median_values() -> None:
    service = RouteStrategyService()
    catalog = _strategy_catalog(include_direct=False)
    travel_date = date(2026, 4, 22)
    catalog = CatalogSnapshot(
        cities=catalog.cities,
        stations=catalog.stations,
        routes=(
            RouteRecord(
                id="ac-low",
                from_station="AS",
                to_station="CS",
                transport_type="train",
                departure_date=travel_date,
                departure_time=time(8, 0),
                arrival_date=travel_date,
                arrival_time=time(10, 0),
                price=90,
                duration_minutes=100,
                company="Rail",
                flight_train_no="G10",
                platform="mock",
            ),
            RouteRecord(
                id="ac-mid",
                from_station="AS",
                to_station="CS",
                transport_type="train",
                departure_date=travel_date,
                departure_time=time(9, 0),
                arrival_date=travel_date,
                arrival_time=time(11, 0),
                price=120,
                duration_minutes=130,
                company="Rail",
                flight_train_no="G11",
                platform="mock",
            ),
            RouteRecord(
                id="ac-high",
                from_station="AS",
                to_station="CS",
                transport_type="train",
                departure_date=travel_date,
                departure_time=time(10, 0),
                arrival_date=travel_date,
                arrival_time=time(12, 0),
                price=300,
                duration_minutes=160,
                company="Rail",
                flight_train_no="G12",
                platform="mock",
            ),
        ),
    )
    request = SearchRequest(
        from_city="A",
        to_city="C",
        travel_date=travel_date,
        optimization_target="balanced",
        max_transfers=0,
    )

    recommendations = service.recommend(
        request=request,
        catalog=catalog,
        from_city_code="A",
        to_city_code="C",
        source_date=travel_date,
        limit=8,
    )

    assert recommendations
    segment = recommendations[0].segments[0]
    assert segment.estimated_price == 120
    assert segment.estimated_duration_minutes == 130
    assert segment.availability.sample_count == 3


def _write_training_csv(root) -> None:
    raw_dir = root / "raw_csv"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        ("A", "B", "Alpha", "Beta", "AS", "BS", "train", "50", "300", "G1"),
        ("A", "B", "Alpha", "Beta", "AS", "BS", "train", "50", "300", "G2"),
        ("B", "C", "Beta", "Gamma", "BS", "CS", "train", "50", "300", "G3"),
        ("B", "C", "Beta", "Gamma", "BS", "CS", "train", "50", "300", "G4"),
        ("A", "C", "Alpha", "Gamma", "AS", "CS", "train", "300", "60", "G5"),
        ("A", "C", "Alpha", "Gamma", "AS", "CS", "train", "300", "60", "G6"),
    ]
    with (raw_dir / "tickets.csv").open("w", encoding="utf-8", newline="") as handle:
        handle.write(
            "from_city_code,to_city_code,from_city,to_city,from_station,to_station,"
            "transport_type,departure_date,departure_time,price,duration_minutes,flight_train_no\n"
        )
        for index, row in enumerate(rows):
            handle.write(
                ",".join([
                    *row[:7],
                    "2026-04-22",
                    f"0{index}:00",
                    row[7],
                    row[8],
                    row[9],
                ])
                + "\n"
            )


def _write_current_format_training_csv(root) -> None:
    raw_dir = root / "raw_csv"
    raw_dir.mkdir(parents=True, exist_ok=True)
    with (raw_dir / "data_train.csv").open("w", encoding="utf-8", newline="") as handle:
        handle.write(
            "provider,type,code,departure,departure_name,departure_city,arrival,arrival_name,"
            "arrival_city,year,date,depart_time,arrive_time,price\n"
        )
        handle.write(
            "12306,train,G137,AS,Alpha Station - 阿站,Alpha - 阿城,BS,Beta Station - 贝站,"
            "Beta - 贝城,2020,01-01,08:00,09:00,0\n"
        )
        handle.write(
            "12306,train,G137,BS,Beta Station - 贝站,Beta - 贝城,CS,Gamma Station - 丙站,"
            "Gamma - 丙城,2020,01-01,09:10,10:20,75\n"
        )
    with (raw_dir / "data_flight.csv").open("w", encoding="utf-8", newline="") as handle:
        handle.write(
            "provider,type,code,departure,departure_name,departure_city,arrival,arrival_name,"
            "arrival_city,year,date,depart_time,arrive_time,price\n"
        )
        handle.write(
            "CA,flight,CA1537,AAA,Alpha Airport - 阿机场,Alpha - 阿城,CCC,Gamma Airport - 丙机场,"
            "Gamma - 丙城,na,na,na,na,580\n"
        )


def _write_train_lines_xlsx(path) -> None:
    rows = [
        ["ID", "车次", "站点名称", "到达时间", "出发时间", "停留时间", "历时（min）", "里程（km）"],
        ["1", "D999", "阿站", "", "08:00:00", "0", "0", "0"],
        ["2", "D999", "贝站", "09:00:00", "09:05:00", "5", "60", "100"],
        ["3", "D999", "丙站", "10:20:00", "10:25:00", "5", "140", "220"],
        ["4", "D999", "丁站", "12:20:00", "", "0", "260", "420"],
    ]
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for col_index, value in enumerate(row, start=1):
            col = chr(ord("A") + col_index - 1)
            cells.append(f'<c r="{col}{row_index}" t="inlineStr"><is><t>{value}</t></is></c>')
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    with zipfile.ZipFile(path, "w") as workbook:
        workbook.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        workbook.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="TrainDetails" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        workbook.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>',
        )
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def _write_ranker_weights(path, *, price_weight: float, duration_weight: float) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = f"test_price_{price_weight}_duration_{duration_weight}"
    payload["weights"].update(
        {
            "price_weight": price_weight,
            "duration_weight": duration_weight,
            "transfer_weight": 0,
            "service_weight": 0,
            "confidence_weight": 0,
            "stability_weight": 0,
            "sample_count_weight": 0,
            "transport_mix_penalty": 0,
        }
    )
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_historical_csv_artifact_and_linear_weights_change_ranking(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "route_training_data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "route_dataset_mode", "historical")
    _write_training_csv(tmp_path)
    build_result = build_route_training_artifacts()
    request_payload = {
        "from_city": "A",
        "to_city": "C",
        "travel_date": "2026-04-22",
        "optimization_target": "balanced",
        "max_transfers": 1,
    }

    _write_ranker_weights(build_result.model_path, price_weight=5, duration_weight=0)
    client = _fresh_client()
    price_response = client.post("/api/v1/search", json=request_payload)
    assert price_response.status_code == 200
    price_payload = price_response.json()
    assert price_payload["route_dataset_mode"] == "historical"
    assert price_payload["route_dataset_version"] == build_result.dataset_version
    assert price_payload["route_model_version"].startswith("test_price_5")
    assert price_payload["recommendations"][0]["city_path"] == ["Alpha", "Beta", "Gamma"]

    _write_ranker_weights(build_result.model_path, price_weight=0, duration_weight=5)
    client = _fresh_client()
    duration_response = client.post("/api/v1/search", json=request_payload)
    assert duration_response.status_code == 200
    duration_payload = duration_response.json()
    assert duration_payload["route_model_version"].startswith("test_price_0")
    assert duration_payload["recommendations"][0]["city_path"] == ["Alpha", "Gamma"]


def test_vehicle_code_normalization() -> None:
    assert normalize_vehicle_code("G137") == "G-137"
    assert normalize_vehicle_code("G-137") == "G-137"
    assert normalize_vehicle_code("G 137") == "G-137"
    assert normalize_vehicle_code("K1471") == "K-1471"
    assert normalize_vehicle_code("C453") == "C-453"
    assert normalize_vehicle_code("CA1537") == "CA-1537"
    assert normalize_vehicle_code("HO1227") == "HO-1227"
    assert normalize_vehicle_code("CA") == "CA-ERR"
    assert normalize_vehicle_code("1537") == "ERR-1537"
    assert normalize_vehicle_code("") == "ERR-ERR"
    assert normalize_vehicle_code("na") == "ERR-ERR"


def test_current_csv_and_train_line_templates_build_historical_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "route_training_data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "route_dataset_mode", "historical")
    _write_current_format_training_csv(tmp_path)
    _write_train_lines_xlsx(tmp_path / "raw_csv" / "2019_lines.xlsx")

    build_result = build_route_training_artifacts()
    assert build_result.accepted_rows > 0
    with gzip.open(build_result.artifact_path, "rt", encoding="utf-8") as handle:
        artifact = json.load(handle)

    metadata = artifact["training_metadata"]
    assert metadata["source_xlsx_files"] == ["2019_lines.xlsx"]
    assert metadata["excel_expanded_segments"] == 6
    assert metadata["excel_accepted_segments"] >= 3
    assert metadata["missing_price_count"] >= 2
    assert metadata["missing_duration_count"] >= 1

    edges = {
        (edge["from_city_code"], edge["to_city_code"], edge["transport_type"]): edge
        for edge in artifact["edges"]
    }
    assert ("ALPHA", "BETA", "train") in edges
    assert ("ALPHA", "GAMMA", "train") in edges
    assert ("ALPHA", "GAMMA", "flight") in edges
    assert edges[("ALPHA", "BETA", "train")]["estimated_price"] > 0
    assert edges[("ALPHA", "BETA", "train")]["estimated_price"] != 0
    assert edges[("ALPHA", "GAMMA", "flight")]["estimated_duration_minutes"] > 0


def test_training_validate_and_evaluate_return_quality_reports(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "route_training_data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "route_dataset_mode", "historical")
    _write_current_format_training_csv(tmp_path)
    _write_train_lines_xlsx(tmp_path / "raw_csv" / "2019_lines.xlsx")
    build_route_training_artifacts()

    validation = validate_route_training_artifact()
    assert validation["status"] == "ok"
    assert validation["edge_count"] > 0
    assert "template_only_edges_present" in validation["warnings"]
    assert validation["top_unmapped_stations"] or validation["template_only_edge_count"] > 0

    evaluation = evaluate_route_training_artifact()
    assert evaluation["status"] == "ok"
    assert evaluation["case_count"] > 0
    assert evaluation["result_rate"] > 0
    assert evaluation["benchmarks"][0]["top_path"]


def test_training_city_alias_merge_drops_self_loops(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "route_training_data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "route_dataset_mode", "historical")
    raw_dir = tmp_path / "raw_csv"
    raw_dir.mkdir(parents=True, exist_ok=True)
    with (raw_dir / "alias.csv").open("w", encoding="utf-8", newline="") as handle:
        handle.write(
            "provider,type,code,departure,departure_name,departure_city,arrival,arrival_name,"
            "arrival_city,year,date,depart_time,arrive_time,price\n"
        )
        handle.write(
            "12306,train,G1,A1,Alpha One - 阿站1,Alpha - 阿城,A2,Alpha Two - 阿站2,"
            "Alt Alpha - 阿城,2020,01-01,08:00,09:00,30\n"
        )
        handle.write(
            "12306,train,G2,A1,Alpha One - 阿站1,Alpha - 阿城,B1,Beta One - 贝站,"
            "Beta - 贝城,2020,01-01,10:00,11:00,70\n"
        )

    build_result = build_route_training_artifacts()
    with gzip.open(build_result.artifact_path, "rt", encoding="utf-8") as handle:
        artifact = json.load(handle)

    metadata = artifact["training_metadata"]
    assert metadata["alias_merged_city_count"] >= 1
    assert metadata["alias_self_loop_dropped_count"] >= 1
    assert all(edge["from_city_code"] != edge["to_city_code"] for edge in artifact["edges"])


def test_route_feedback_and_annotation_flow() -> None:
    client = _fresh_client()
    headers = _ai_headers(client)
    feedback_response = client.post(
        "/api/v1/search/feedback",
        headers=headers,
        json={
            "search_id": "search_test",
            "recommendation_id": "strategy_A_C",
            "action": "negative",
            "comment": "Too many transfers.",
            "source": "search",
            "feedback_context": "route_card",
            "ratings": {
                "overall": 2,
                "route_reasonable": 2,
                "cost_trustworthy": 3,
                "transfer_clear": 2,
            },
            "search_request": {"from_city": "A", "to_city": "C"},
            "recommendation": {"city_path": ["A", "B", "C"]},
            "model_version": "linear_ranker_v1",
            "dataset_version": "historical_test",
        },
    )
    assert feedback_response.status_code == 200
    feedback_id = feedback_response.json()["id"]

    annotation_response = client.put(
        f"/api/v1/search/feedback/{feedback_id}/annotation",
        headers=headers,
        json={
            "label": "bad",
            "issues": ["too_many_transfers", "too_slow"],
            "notes": "Prefer direct route.",
        },
    )
    assert annotation_response.status_code == 200
    assert annotation_response.json()["label"] == "bad"

    export_response = client.get("/api/v1/search/feedback/annotated", headers=headers)
    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert export_payload["total"] >= 1
    assert export_payload["samples"][0]["annotation"]["label"] == "bad"


def test_anonymous_route_feedback_requires_session_and_accepts_ratings() -> None:
    client = _fresh_client()
    missing_session_response = client.post(
        "/api/v1/search/feedback",
        json={
            "search_id": "search_test",
            "recommendation_id": "strategy_A_C",
            "action": "selected",
            "source": "ai",
            "feedback_context": "ai_experience",
            "ratings": {
                "overall": 5,
                "route_reasonable": 4,
                "cost_trustworthy": 4,
                "transfer_clear": 5,
            },
        },
    )
    assert missing_session_response.status_code == 400

    feedback_response = client.post(
        "/api/v1/search/feedback",
        json={
            "search_id": "search_test",
            "recommendation_id": "strategy_A_C",
            "anonymous_session_id": "anon_test_session",
            "action": "selected",
            "source": "ai",
            "feedback_context": "ai_experience",
            "ratings": {
                "overall": 5,
                "route_reasonable": 4,
                "cost_trustworthy": 4,
                "transfer_clear": 5,
            },
            "selected_recommendation_ids": ["strategy_A_C", "strategy_A_B_C"],
            "clicked_provider": "ctrip",
            "clicked_segment_index": 0,
            "comment": "The first option worked well.",
        },
    )
    assert feedback_response.status_code == 200
    assert feedback_response.json()["id"].startswith("feedback_")


def test_strategy_recommends_transfer_when_no_direct_baseline_exists() -> None:
    service = RouteStrategyService()
    request = SearchRequest(
        from_city="A",
        to_city="C",
        travel_date=date(2026, 4, 22),
        optimization_target="balanced",
        max_transfers=1,
    )

    recommendations = service.recommend(
        request=request,
        catalog=_strategy_catalog(include_direct=False),
        from_city_code="A",
        to_city_code="C",
        source_date=date(2026, 4, 22),
        limit=8,
    )

    assert recommendations
    assert recommendations[0].city_path == ["Alpha", "Beta", "Gamma"]
    assert recommendations[0].transfer_count == 1


def _mock_deepseek_multi_turn(monkeypatch) -> None:
    def fake_respond(self, *, conversation, draft_request, cities, language="zh"):
        last_message = conversation[-1].content
        if "预算3000" in last_message:
            return type(
                "Turn",
                (),
                {
                    "assistant_message": "我已整理好条件：北京到成都，2026-04-22出发，只坐飞机，预算1300元以内。请确认是否开始搜索？",
                    "extracted_request": {
                        "from_city": "北京",
                        "to_city": "成都",
                        "travel_date": "2026-04-22",
                        "preferred_transport_types": ["flight"],
                        "max_price": 3000,
                        "optimization_target": "price",
                        "max_transfers": 0,
                    },
                    "should_confirm": True,
                    "summary": "已确认出发地、日期、预算和交通偏好。",
                },
            )()

        return type(
            "Turn",
            (),
            {
                "assistant_message": "可以，先告诉我你从哪个城市出发、哪天走。如果你有预算或交通方式偏好，也可以一起说。",
                "extracted_request": {
                    "to_city": "成都",
                    "optimization_target": "price",
                },
                "should_confirm": False,
                "summary": "已识别目的地成都和价格优先偏好。",
            },
        )()

    monkeypatch.setattr(
        "app.agents.ai_agent.DeepSeekChatClient.respond",
        fake_respond,
    )


def test_ai_search_collects_fields_across_turns_and_executes_on_confirm(monkeypatch) -> None:
    _mock_deepseek_multi_turn(monkeypatch)
    client = _fresh_client()
    headers = _ai_headers(client)
    create_response = client.post(
        "/api/v1/search/ai/sessions",
        headers=headers,
        json={"message": "我想去成都，越便宜越好"},
    )

    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["status"] == "collecting_required"
    assert create_payload["search_executed"] is False
    assert "from_city" in create_payload["missing_fields"]
    assert "travel_date" in create_payload["missing_fields"]
    assert create_payload["parsed_request"]["to_city"] == "成都"
    assert create_payload["ready_for_confirmation"] is False
    assert create_payload["search_response"] is None

    session_id = create_payload["session_id"]
    message_response = client.post(
        f"/api/v1/search/ai/sessions/{session_id}/messages",
        headers=headers,
        json={"message": "我从北京出发，2026-04-22走，只坐飞机，预算3000元以内"},
    )

    assert message_response.status_code == 200
    message_payload = message_response.json()
    assert message_payload["status"] == "awaiting_confirmation"
    assert message_payload["missing_fields"] == []
    assert message_payload["ready_for_confirmation"] is True
    assert message_payload["final_request"]["from_city"] == "北京"
    assert message_payload["final_request"]["to_city"] == "成都"
    assert message_payload["final_request"]["preferred_transport_types"] == ["flight"]
    assert message_payload["final_request"]["max_price"] == 3000
    assert message_payload["search_executed"] is False

    confirm_response = client.post(
        f"/api/v1/search/ai/sessions/{session_id}/confirm",
        headers=headers,
        json={"confirmed": True},
    )

    assert confirm_response.status_code == 200
    confirm_payload = confirm_response.json()
    assert confirm_payload["status"] == "results_available"
    assert confirm_payload["search_executed"] is True
    assert confirm_payload["search_response"]["result_mode"] == "strategy"
    route = confirm_payload["search_response"]["recommendations"][0]
    assert route["estimated_total_price"] <= 3000
    assert all(segment["recommended_transport_type"] == "flight" for segment in route["segments"])


def test_ai_search_can_continue_after_user_rejects_confirmation(monkeypatch) -> None:
    _mock_deepseek_multi_turn(monkeypatch)
    client = _fresh_client()
    headers = _ai_headers(client)
    create_response = client.post(
        "/api/v1/search/ai/sessions",
        headers=headers,
        json={"message": "我想去成都，越便宜越好"},
    )
    session_id = create_response.json()["session_id"]

    client.post(
        f"/api/v1/search/ai/sessions/{session_id}/messages",
        headers=headers,
        json={"message": "我从北京出发，2026-04-22走，只坐飞机，预算3000元以内"},
    )
    reject_response = client.post(
        f"/api/v1/search/ai/sessions/{session_id}/confirm",
        headers=headers,
        json={"confirmed": False},
    )

    assert reject_response.status_code == 200
    reject_payload = reject_response.json()
    assert reject_payload["status"] == "awaiting_confirmation"
    assert reject_payload["search_executed"] is False
    assert "继续调整条件" in reject_payload["assistant_message"]
