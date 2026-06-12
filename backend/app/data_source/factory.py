from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.data_source.base import DataSourceBase
from app.data_source.mock_adapter import MockAdapter
from app.data_source.repository import (
    HistoricalArtifactCatalogRepository,
    InMemoryCatalogRepository,
    MySQLCatalogRepository,
)


@lru_cache
def create_data_source() -> DataSourceBase:
    source_type = settings.data_source.lower()

    if source_type == "mock":
        from app.services.route_training import select_route_dataset

        selection = select_route_dataset()
        if selection.mode == "historical" and selection.artifact_path is not None:
            return MockAdapter(
                primary_repository=HistoricalArtifactCatalogRepository(selection.artifact_path),
                fallback_repository=InMemoryCatalogRepository(),
                source_label="historical",
                source_warning=selection.warning,
            )
        return MockAdapter(
            primary_repository=MySQLCatalogRepository(settings.database_url),
            fallback_repository=InMemoryCatalogRepository(),
            source_warning=selection.warning,
        )

    if source_type in {"scraper", "api"}:
        raise NotImplementedError(
            f"Data source '{settings.data_source}' is reserved for later phases and is not implemented yet."
        )

    raise ValueError(f"Unknown data source type: {settings.data_source}")


def reset_data_source_cache() -> None:
    create_data_source.cache_clear()
