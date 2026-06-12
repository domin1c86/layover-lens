from __future__ import annotations

from threading import Lock
from typing import Optional

from app.data_source.base import CatalogSnapshot, CityRecord, DataSourceBase
from app.data_source.repository import CatalogRepository, RepositoryUnavailableError


class MockAdapter(DataSourceBase):
    def __init__(
        self,
        primary_repository: CatalogRepository,
        fallback_repository: Optional[CatalogRepository] = None,
        source_label: str = "mock",
        source_warning: str = "",
    ) -> None:
        self._primary_repository = primary_repository
        self._fallback_repository = fallback_repository
        self._source_label = source_label
        self._source_warning = source_warning
        self._catalog: Optional[CatalogSnapshot] = None
        self._backend_description: Optional[str] = None
        self._lock = Lock()

    def get_cities(self, keyword: Optional[str] = None) -> list[CityRecord]:
        cities = list(self.get_catalog().cities)
        if not keyword:
            return cities

        normalized = keyword.strip().lower()
        return [
            city
            for city in cities
            if normalized in city.code.lower()
            or normalized in city.name.lower()
            or normalized in city.name_en.lower()
        ]

    def get_catalog(self) -> CatalogSnapshot:
        if self._catalog is not None:
            return self._catalog

        with self._lock:
            if self._catalog is not None:
                return self._catalog

            try:
                self._catalog = self._primary_repository.load_catalog()
                self._backend_description = self._primary_repository.describe()
            except RepositoryUnavailableError:
                if self._fallback_repository is None:
                    raise
                self._catalog = self._fallback_repository.load_catalog()
                self._backend_description = self._fallback_repository.describe()

            return self._catalog

    def describe_source(self) -> str:
        if self._backend_description is None:
            self.get_catalog()
        suffix = f":{self._source_warning}" if self._source_warning else ""
        return f"{self._source_label}:{self._backend_description}{suffix}"
