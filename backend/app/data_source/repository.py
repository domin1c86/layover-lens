from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time, timedelta
from urllib.parse import unquote, urlparse

from app.data_source.base import CatalogSnapshot, CityRecord, RouteRecord, StationRecord


class RepositoryUnavailableError(RuntimeError):
    pass


def _parse_clock(value: str) -> time:
    hours, minutes, *seconds = [int(part) for part in value.split(":")]
    second = seconds[0] if seconds else 0
    return time(hour=hours, minute=minutes, second=second)


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _coerce_time(value: object) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds()) % (24 * 60 * 60)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return time(hour=hours, minute=minutes, second=seconds)
    if isinstance(value, str):
        return _parse_clock(value)
    raise RepositoryUnavailableError(f"Unsupported TIME value: {value!r}")


def _coerce_date(value: object) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return _parse_date(value)
    raise RepositoryUnavailableError(f"Unsupported DATE value: {value!r}")


class CatalogRepository:
    def load_catalog(self) -> CatalogSnapshot:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError


class InMemoryCatalogRepository(CatalogRepository):
    def __init__(self) -> None:
        seed_date = _parse_date("2026-04-22")
        self._catalog = CatalogSnapshot(
            cities=(
                CityRecord(code="BJ", name="北京", name_en="Beijing"),
                CityRecord(code="SH", name="上海", name_en="Shanghai"),
                CityRecord(code="NJ", name="南京", name_en="Nanjing"),
                CityRecord(code="WH", name="武汉", name_en="Wuhan"),
                CityRecord(code="XA", name="西安", name_en="Xi'an"),
                CityRecord(code="CD", name="成都", name_en="Chengdu"),
                CityRecord(code="GZ", name="广州", name_en="Guangzhou"),
                CityRecord(code="SZ", name="深圳", name_en="Shenzhen"),
            ),
            stations=(
                StationRecord(code="PEK", name="首都国际机场", city_code="BJ", station_type="airport", name_en="Capital International Airport"),
                StationRecord(code="BJS", name="北京南站", city_code="BJ", station_type="train_station", name_en="Beijing South Railway Station"),
                StationRecord(code="PVG", name="浦东国际机场", city_code="SH", station_type="airport", name_en="Pudong International Airport"),
                StationRecord(code="SHH", name="上海虹桥站", city_code="SH", station_type="train_station", name_en="Shanghai Hongqiao Railway Station"),
                StationRecord(code="NKG", name="禄口国际机场", city_code="NJ", station_type="airport", name_en="Lukou International Airport"),
                StationRecord(code="NJS", name="南京南站", city_code="NJ", station_type="train_station", name_en="Nanjing South Railway Station"),
                StationRecord(code="WUH", name="天河国际机场", city_code="WH", station_type="airport", name_en="Tianhe International Airport"),
                StationRecord(code="WHH", name="汉口站", city_code="WH", station_type="train_station", name_en="Hankou Railway Station"),
                StationRecord(code="XIY", name="咸阳国际机场", city_code="XA", station_type="airport", name_en="Xianyang International Airport"),
                StationRecord(code="XAS", name="西安北站", city_code="XA", station_type="train_station", name_en="Xi'an North Railway Station"),
                StationRecord(code="CTU", name="双流国际机场", city_code="CD", station_type="airport", name_en="Shuangliu International Airport"),
                StationRecord(code="CDS", name="成都东站", city_code="CD", station_type="train_station", name_en="Chengdu East Railway Station"),
                StationRecord(code="CAN", name="白云国际机场", city_code="GZ", station_type="airport", name_en="Baiyun International Airport"),
                StationRecord(code="GZS", name="广州南站", city_code="GZ", station_type="train_station", name_en="Guangzhou South Railway Station"),
                StationRecord(code="SZX", name="宝安国际机场", city_code="SZ", station_type="airport", name_en="Bao'an International Airport"),
                StationRecord(code="SZS", name="深圳北站", city_code="SZ", station_type="train_station", name_en="Shenzhen North Railway Station"),
            ),
            routes=(
                RouteRecord(
                    id="PEK-CTU-CA1861",
                    from_station="PEK",
                    to_station="CTU",
                    transport_type="flight",
                    departure_date=seed_date,
                    departure_time=_parse_clock("08:00"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("11:05"),
                    price=860.0,
                    duration_minutes=185,
                    company="中国国航",
                    flight_train_no="CA1861",
                    platform="ctrip",
                ),
                RouteRecord(
                    id="BJS-CDS-G87",
                    from_station="BJS",
                    to_station="CDS",
                    transport_type="train",
                    departure_date=seed_date,
                    departure_time=_parse_clock("09:00"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("20:58"),
                    price=780.0,
                    duration_minutes=718,
                    company="中国铁路",
                    flight_train_no="G87",
                    platform="12306",
                ),
                RouteRecord(
                    id="PEK-XIY-MU2201",
                    from_station="PEK",
                    to_station="XIY",
                    transport_type="flight",
                    departure_date=seed_date,
                    departure_time=_parse_clock("07:30"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("09:40"),
                    price=460.0,
                    duration_minutes=130,
                    company="东方航空",
                    flight_train_no="MU2201",
                    platform="qunar",
                ),
                RouteRecord(
                    id="XAS-CDS-D1911",
                    from_station="XAS",
                    to_station="CDS",
                    transport_type="train",
                    departure_date=seed_date,
                    departure_time=_parse_clock("11:30"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("15:28"),
                    price=263.0,
                    duration_minutes=238,
                    company="中国铁路",
                    flight_train_no="D1911",
                    platform="12306",
                ),
                RouteRecord(
                    id="PEK-WUH-CZ3137",
                    from_station="PEK",
                    to_station="WUH",
                    transport_type="flight",
                    departure_date=seed_date,
                    departure_time=_parse_clock("09:00"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("11:10"),
                    price=560.0,
                    duration_minutes=130,
                    company="南方航空",
                    flight_train_no="CZ3137",
                    platform="fliggy",
                ),
                RouteRecord(
                    id="WHH-CDS-G345",
                    from_station="WHH",
                    to_station="CDS",
                    transport_type="train",
                    departure_date=seed_date,
                    departure_time=_parse_clock("13:00"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("18:32"),
                    price=410.0,
                    duration_minutes=332,
                    company="中国铁路",
                    flight_train_no="G345",
                    platform="12306",
                ),
                RouteRecord(
                    id="PEK-NKG-MU2811",
                    from_station="PEK",
                    to_station="NKG",
                    transport_type="flight",
                    departure_date=seed_date,
                    departure_time=_parse_clock("08:20"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("10:30"),
                    price=520.0,
                    duration_minutes=130,
                    company="东方航空",
                    flight_train_no="MU2811",
                    platform="ctrip",
                ),
                RouteRecord(
                    id="NJS-CDS-D2241",
                    from_station="NJS",
                    to_station="CDS",
                    transport_type="train",
                    departure_date=seed_date,
                    departure_time=_parse_clock("12:25"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("19:18"),
                    price=420.0,
                    duration_minutes=413,
                    company="中国铁路",
                    flight_train_no="D2241",
                    platform="12306",
                ),
                RouteRecord(
                    id="PEK-PVG-CA1501",
                    from_station="PEK",
                    to_station="PVG",
                    transport_type="flight",
                    departure_date=seed_date,
                    departure_time=_parse_clock("07:00"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("09:20"),
                    price=850.0,
                    duration_minutes=140,
                    company="中国国航",
                    flight_train_no="CA1501",
                    platform="ctrip",
                ),
                RouteRecord(
                    id="SHH-CDS-G2191",
                    from_station="SHH",
                    to_station="CDS",
                    transport_type="train",
                    departure_date=seed_date,
                    departure_time=_parse_clock("12:00"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("22:31"),
                    price=630.0,
                    duration_minutes=631,
                    company="中国铁路",
                    flight_train_no="G2191",
                    platform="12306",
                ),
                RouteRecord(
                    id="CAN-SZX-CZ3351",
                    from_station="CAN",
                    to_station="SZX",
                    transport_type="flight",
                    departure_date=seed_date,
                    departure_time=_parse_clock("10:00"),
                    arrival_date=seed_date,
                    arrival_time=_parse_clock("11:10"),
                    price=320.0,
                    duration_minutes=70,
                    company="南方航空",
                    flight_train_no="CZ3351",
                    platform="fliggy",
                ),
            ),
        )

    def load_catalog(self) -> CatalogSnapshot:
        return self._catalog

    def describe(self) -> str:
        return "memory"


@dataclass(frozen=True)
class ParsedDatabaseUrl:
    host: str
    port: int
    user: str
    password: str
    database: str


class MySQLCatalogRepository(CatalogRepository):
    def __init__(self, database_url: str) -> None:
        self._config = self._parse_url(database_url)

    def describe(self) -> str:
        return "mysql"

    def load_catalog(self) -> CatalogSnapshot:
        try:
            import mysql.connector
        except ImportError as exc:
            raise RepositoryUnavailableError("mysql-connector-python is not installed") from exc

        try:
            connection = mysql.connector.connect(
                host=self._config.host,
                port=self._config.port,
                user=self._config.user,
                password=self._config.password,
                database=self._config.database,
                charset="utf8mb4",
                collation="utf8mb4_general_ci",
                use_unicode=True,
            )
        except mysql.connector.Error as exc:
            raise RepositoryUnavailableError(f"MySQL connection failed: {exc}") from exc

        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT code, name, COALESCE(name_en, '') AS name_en, COALESCE(country, '中国') AS country
                FROM cities
                ORDER BY code
                """
            )
            cities = tuple(
                CityRecord(
                    code=row["code"],
                    name=row["name"],
                    name_en=row["name_en"],
                    country=row["country"],
                )
                for row in cursor.fetchall()
            )

            cursor.execute(
                """
                SELECT code, name, name_en, city_code, type
                FROM stations
                ORDER BY code
                """
            )
            stations = tuple(
                StationRecord(
                    code=row["code"],
                    name=row["name"],
                    city_code=row["city_code"],
                    station_type=row["type"],
                    name_en=row["name_en"] or "",
                )
                for row in cursor.fetchall()
            )

            cursor.execute(
                """
                SELECT
                    from_station,
                    to_station,
                    transport_type,
                    departure_date,
                    departure_time,
                    arrival_date,
                    arrival_time,
                    price,
                    duration_minutes,
                    COALESCE(company, '') AS company,
                    COALESCE(flight_train_no, '') AS flight_train_no,
                    COALESCE(platform, '') AS platform
                FROM routes
                ORDER BY from_station, to_station, departure_date, departure_time, flight_train_no
                """
            )
            routes = tuple(
                RouteRecord(
                    id=(
                        f"{row['from_station']}-{row['to_station']}-"
                        f"{row['flight_train_no']}-{row['departure_date']}-{row['departure_time']}"
                    ),
                    from_station=row["from_station"],
                    to_station=row["to_station"],
                    transport_type=row["transport_type"],
                    departure_date=_coerce_date(row["departure_date"]),
                    departure_time=_coerce_time(row["departure_time"]),
                    arrival_date=_coerce_date(row["arrival_date"]),
                    arrival_time=_coerce_time(row["arrival_time"]),
                    price=float(row["price"]),
                    duration_minutes=int(row["duration_minutes"]),
                    company=row["company"],
                    flight_train_no=row["flight_train_no"],
                    platform=row["platform"],
                )
                for row in cursor.fetchall()
            )

            return CatalogSnapshot(cities=cities, stations=stations, routes=routes)
        finally:
            connection.close()

    @staticmethod
    def _parse_url(database_url: str) -> ParsedDatabaseUrl:
        parsed = urlparse(database_url)
        database = parsed.path.lstrip("/")
        if not database:
            raise RepositoryUnavailableError("DATABASE_URL is missing the database name")

        return ParsedDatabaseUrl(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=unquote(parsed.username or "root"),
            password=unquote(parsed.password or ""),
            database=database,
        )
