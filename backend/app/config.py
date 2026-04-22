from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="Layover Lens API", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    database_url: str = Field(
        default="mysql+mysqlconnector://root:devpassword@mysql:3306/layover_lens",
        alias="DATABASE_URL",
    )
    data_source: str = Field(default="mock", alias="DATA_SOURCE")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="CORS_ORIGINS",
    )
    max_routes: int = Field(default=8, alias="MAX_ROUTES")
    default_max_transfers: int = Field(default=2, alias="DEFAULT_MAX_TRANSFERS")
    min_transfer_minutes_same_station: int = Field(
        default=45,
        alias="MIN_TRANSFER_MINUTES_SAME_STATION",
    )
    min_transfer_minutes_same_city: int = Field(
        default=90,
        alias="MIN_TRANSFER_MINUTES_SAME_CITY",
    )
    max_layover_minutes: int = Field(default=480, alias="MAX_LAYOVER_MINUTES")
    max_total_duration_minutes: int = Field(
        default=24 * 60,
        alias="MAX_TOTAL_DURATION_MINUTES",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
