from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional

from app.data_source.base import CityRecord
from app.schemas import OptimizationTarget, ParsedSearchRequest, TimeRange, TransportType


@dataclass(frozen=True)
class _CityAlias:
    alias: str
    canonical_name: str


class RuleBasedQueryParser:
    def parse(
        self,
        query: str,
        cities: Iterable[CityRecord],
        *,
        today: Optional[date] = None,
    ) -> ParsedSearchRequest:
        today = today or date.today()
        aliases = self._build_city_aliases(cities)
        parsed = ParsedSearchRequest(
            optimization_target=self._extract_optimization_target(query),
            allow_overnight=self._extract_allow_overnight(query),
        )

        from_city, to_city = self._extract_route_pair(query, aliases)
        parsed.from_city = from_city
        parsed.to_city = to_city
        parsed.travel_date = self._extract_date(query, today=today)
        parsed.max_price = self._extract_max_price(query)
        parsed.max_total_duration_minutes = self._extract_max_total_duration_minutes(query)
        parsed.max_transfers = self._extract_max_transfers(query)
        parsed.preferred_transport_types = self._extract_transport_types(query)
        parsed.excluded_cities = self._extract_excluded_cities(query, aliases)
        parsed.required_transfer_cities = self._extract_required_transfer_cities(query, aliases)
        parsed.departure_time_range = self._extract_time_range(query, "departure")
        parsed.arrival_time_range = self._extract_time_range(query, "arrival")

        if parsed.preferred_transport_types == [TransportType.FLIGHT] and "直飞" in query:
            parsed.max_transfers = 0
        if "直达" in query:
            parsed.max_transfers = 0

        return parsed

    @staticmethod
    def missing_fields(parsed: ParsedSearchRequest) -> list[str]:
        missing = []
        if not parsed.from_city:
            missing.append("from_city")
        if not parsed.to_city:
            missing.append("to_city")
        if not parsed.travel_date:
            missing.append("travel_date")
        return missing

    def _build_city_aliases(self, cities: Iterable[CityRecord]) -> list[_CityAlias]:
        aliases: dict[str, str] = {}
        for city in cities:
            candidates = {
                city.code,
                city.name,
                city.name_en,
            }
            for candidate in candidates:
                normalized = candidate.strip().lower()
                if normalized:
                    aliases[normalized] = city.name
        return sorted(
            (_CityAlias(alias=alias, canonical_name=name) for alias, name in aliases.items()),
            key=lambda item: len(item.alias),
            reverse=True,
        )

    def _extract_route_pair(
        self,
        query: str,
        aliases: list[_CityAlias],
    ) -> tuple[Optional[str], Optional[str]]:
        lowered = query.lower()
        from_index = lowered.find("从")
        to_index = lowered.find("到", from_index + 1 if from_index >= 0 else 0)

        if from_index >= 0 and to_index > from_index:
            from_city = self._find_first_city_in_span(lowered, aliases, from_index + 1, to_index)
            to_city = self._find_first_city_in_span(lowered, aliases, to_index + 1, len(lowered))
            if from_city or to_city:
                return from_city, to_city

        city_mentions = self._find_city_mentions(lowered, aliases)
        if len(city_mentions) >= 2:
            return city_mentions[0], city_mentions[1]
        if len(city_mentions) == 1 and any(keyword in query for keyword in ("去", "到")):
            return None, city_mentions[0]
        return None, None

    def _find_city_mentions(
        self,
        lowered_query: str,
        aliases: list[_CityAlias],
    ) -> list[str]:
        matches: list[tuple[int, str]] = []
        seen_positions: set[tuple[int, str]] = set()
        for item in aliases:
            start = 0
            while True:
                index = lowered_query.find(item.alias, start)
                if index < 0:
                    break
                key = (index, item.canonical_name)
                if key not in seen_positions:
                    matches.append((index, item.canonical_name))
                    seen_positions.add(key)
                start = index + len(item.alias)

        matches.sort(key=lambda item: item[0])
        ordered: list[str] = []
        for _, city_name in matches:
            if city_name not in ordered:
                ordered.append(city_name)
        return ordered

    def _find_first_city_in_span(
        self,
        lowered_query: str,
        aliases: list[_CityAlias],
        start_index: int,
        end_index: int,
    ) -> Optional[str]:
        span = lowered_query[start_index:end_index]
        best_match: Optional[tuple[int, str]] = None
        for item in aliases:
            position = span.find(item.alias)
            if position < 0:
                continue
            if best_match is None or position < best_match[0]:
                best_match = (position, item.canonical_name)
        return best_match[1] if best_match is not None else None

    def _extract_date(self, query: str, *, today: date) -> Optional[date]:
        if match := re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})", query):
            year, month, day = [int(part) for part in match.groups()]
            return date(year, month, day)

        if match := re.search(r"(\d{1,2})月(\d{1,2})日", query):
            month, day = [int(part) for part in match.groups()]
            year = today.year
            candidate = date(year, month, day)
            if candidate < today:
                candidate = date(year + 1, month, day)
            return candidate

        if "今天" in query:
            return today
        if "明天" in query:
            return today + timedelta(days=1)
        if "后天" in query:
            return today + timedelta(days=2)

        return None

    def _extract_optimization_target(self, query: str) -> OptimizationTarget:
        if any(keyword in query for keyword in ("最便宜", "便宜", "省钱", "预算")):
            return OptimizationTarget.PRICE
        if any(keyword in query for keyword in ("最快", "最短", "赶时间", "尽快", "快一点")):
            return OptimizationTarget.TIME
        if any(keyword in query for keyword in ("少换乘", "最少换乘", "直达", "直飞")):
            return OptimizationTarget.TRANSFER
        return OptimizationTarget.BALANCED

    def _extract_transport_types(self, query: str) -> Optional[list[TransportType]]:
        if any(keyword in query for keyword in ("只坐飞机", "只要飞机", "直飞", "航班")):
            return [TransportType.FLIGHT]
        if any(keyword in query for keyword in ("只坐火车", "只坐高铁", "只要高铁", "只要火车")):
            return [TransportType.TRAIN]
        return None

    def _extract_max_price(self, query: str) -> Optional[float]:
        patterns = [
            r"预算\s*(\d+(?:\.\d+)?)",
            r"不超过\s*(\d+(?:\.\d+)?)\s*元",
            r"(\d+(?:\.\d+)?)\s*元以内",
            r"低于\s*(\d+(?:\.\d+)?)\s*元",
        ]
        for pattern in patterns:
            if match := re.search(pattern, query):
                return float(match.group(1))
        return None

    def _extract_max_total_duration_minutes(self, query: str) -> Optional[int]:
        patterns = [
            r"(?:总时长|全程|耗时|时间)\s*(?:不超过|少于|小于|控制在)?\s*(\d+)\s*小时",
            r"(\d+)\s*小时内",
        ]
        for pattern in patterns:
            if match := re.search(pattern, query):
                return int(match.group(1)) * 60
        return None

    def _extract_max_transfers(self, query: str) -> Optional[int]:
        if "直飞" in query or "直达" in query:
            return 0
        if match := re.search(r"(?:最多|至多|不超过)\s*(\d+)\s*次?(?:换乘|中转)", query):
            return int(match.group(1))
        if match := re.search(r"(\d+)\s*次?(?:换乘|中转)以内", query):
            return int(match.group(1))
        return None

    def _extract_excluded_cities(
        self,
        query: str,
        aliases: list[_CityAlias],
    ) -> list[str]:
        results: list[str] = []
        patterns = [
            r"(?:不要经过|不经过|避开|排除)([^，。；,.!?！？]+)",
            r"(?:不要在)([^，。；,.!?！？]+?)(?:中转|转机|转车)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, query):
                results.extend(self._extract_city_names_from_text(match.group(1), aliases))
        return self._dedupe(results)

    def _extract_required_transfer_cities(
        self,
        query: str,
        aliases: list[_CityAlias],
    ) -> list[str]:
        results: list[str] = []
        patterns = [
            r"(?:经由|经|经过)([^，。；,.!?！？]+?)(?:中转|转机|转车)",
            r"(?:在)([^，。；,.!?！？]+?)(?:中转|转机|转车)",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, query):
                results.extend(self._extract_city_names_from_text(match.group(1), aliases))
        return self._dedupe(results)

    def _extract_time_range(self, query: str, mode: str) -> Optional[TimeRange]:
        suffix = "出发" if mode == "departure" else "到达"
        if match := re.search(
            rf"(\d{{1,2}}(?::\d{{2}}|点(?:半|[0-5]?\d分?)?)?)[到\-](\d{{1,2}}(?::\d{{2}}|点(?:半|[0-5]?\d分?)?)?)(?:之间)?{suffix}",
            query,
        ):
            start = self._parse_time_expression(match.group(1))
            end = self._parse_time_expression(match.group(2))
            if start and end:
                return TimeRange(start=start, end=end)

        if match := re.search(
            rf"(\d{{1,2}}(?::\d{{2}}|点(?:半|[0-5]?\d分?)?)?)(?:之后|以后|后){suffix}",
            query,
        ):
            start = self._parse_time_expression(match.group(1))
            if start:
                return TimeRange(start=start, end="23:59")

        if match := re.search(
            rf"(\d{{1,2}}(?::\d{{2}}|点(?:半|[0-5]?\d分?)?)?)(?:之前|以前|前){suffix}",
            query,
        ):
            end = self._parse_time_expression(match.group(1))
            if end:
                return TimeRange(start="00:00", end=end)

        keyword_mapping = {
            "上午": ("06:00", "11:59"),
            "早上": ("06:00", "11:59"),
            "中午": ("11:00", "13:59"),
            "下午": ("12:00", "17:59"),
            "晚上": ("18:00", "23:59"),
            "凌晨": ("00:00", "05:59"),
        }
        for keyword, (start, end) in keyword_mapping.items():
            if f"{keyword}{suffix}" in query:
                return TimeRange(start=start, end=end)

        return None

    def _extract_allow_overnight(self, query: str) -> bool:
        if any(keyword in query for keyword in ("不要过夜", "不想过夜", "不要红眼", "当天到达")):
            return False
        return True

    def _extract_city_names_from_text(
        self,
        text: str,
        aliases: list[_CityAlias],
    ) -> list[str]:
        lowered = text.lower()
        results: list[str] = []
        for item in aliases:
            if item.alias in lowered and item.canonical_name not in results:
                results.append(item.canonical_name)
        return results

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

    def _parse_time_expression(self, raw_value: str) -> Optional[str]:
        raw_value = raw_value.strip()
        if re.fullmatch(r"\d{1,2}:\d{2}", raw_value):
            hours, minutes = [int(part) for part in raw_value.split(":")]
            if hours in range(24) and minutes in range(60):
                return f"{hours:02d}:{minutes:02d}"
            return None

        if match := re.fullmatch(r"(\d{1,2})点半", raw_value):
            hours = int(match.group(1))
            if hours in range(24):
                return f"{hours:02d}:30"
            return None

        if match := re.fullmatch(r"(\d{1,2})点(?:(\d{1,2})分?)?", raw_value):
            hours = int(match.group(1))
            minutes = int(match.group(2) or "0")
            if hours in range(24) and minutes in range(60):
                return f"{hours:02d}:{minutes:02d}"

        return None
