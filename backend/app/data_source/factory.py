from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.data_source.base import DataSourceBase
from app.data_source.mock_adapter import MockAdapter
from app.data_source.repository import InMemoryCatalogRepository, MySQLCatalogRepository


@lru_cache
def create_data_source() -> DataSourceBase:
    source_type = settings.data_source.lower()

    if source_type == "mock":
        return MockAdapter(
            primary_repository=MySQLCatalogRepository(settings.database_url),
            fallback_repository=InMemoryCatalogRepository(),
        )

    if source_type in {"scraper", "api"}:
        raise NotImplementedError(
            f"Data source '{settings.data_source}' is reserved for later phases and is not implemented yet."
        )

    raise ValueError(f"Unknown data source type: {settings.data_source}")


def reset_data_source_cache() -> None:
    create_data_source.cache_clear()
