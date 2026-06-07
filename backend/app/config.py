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
    app_env: str = Field(default="development", alias="APP_ENV")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    database_url: str = Field(
        default="mysql+mysqlconnector://root:devpassword@mysql:3306/layover_lens",
        alias="DATABASE_URL",
    )
    data_source: str = Field(default="mock", alias="DATA_SOURCE")
    route_training_data_dir: str = Field(
        default="backend/data/route_training",
        alias="ROUTE_TRAINING_DATA_DIR",
    )
    route_dataset_mode: str = Field(default="auto", alias="ROUTE_DATASET_MODE")
    route_planner_backend: str = Field(default="auto", alias="ROUTE_PLANNER_BACKEND")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="CORS_ORIGINS",
    )
    auth_cookie_name: str = Field(default="layover_lens_session", alias="AUTH_COOKIE_NAME")
    csrf_cookie_name: str = Field(default="layover_lens_csrf", alias="CSRF_COOKIE_NAME")
    csrf_header_name: str = Field(default="X-CSRF-Token", alias="CSRF_HEADER_NAME")
    session_cookie_secret: str = Field(default="dev-session-cookie-secret", alias="SESSION_COOKIE_SECRET")
    csrf_secret: str = Field(default="dev-csrf-secret", alias="CSRF_SECRET")
    totp_encryption_secret: str = Field(default="dev-totp-encryption-secret", alias="TOTP_ENCRYPTION_SECRET")
    totp_issuer_name: str = Field(default="Layover Lens", alias="TOTP_ISSUER_NAME")
    session_cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")
    session_cookie_samesite: str = Field(default="lax", alias="SESSION_COOKIE_SAMESITE")
    disable_bearer_auth_in_production: bool = Field(default=True, alias="DISABLE_BEARER_AUTH_IN_PRODUCTION")
    rate_limit_window_seconds: int = Field(default=300, alias="RATE_LIMIT_WINDOW_SECONDS")
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
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        alias="DEEPSEEK_BASE_URL",
    )
    deepseek_model: str = Field(default="deepseek-v4-pro", alias="DEEPSEEK_MODEL")
    deepseek_timeout_seconds: float = Field(
        default=30.0,
        alias="DEEPSEEK_TIMEOUT_SECONDS",
    )
    ai_model_provider: str = Field(default="deepseek", alias="AI_MODEL_PROVIDER")
    ai_model_api_key: str = Field(default="", alias="AI_MODEL_API_KEY")
    ai_model_base_url: str = Field(default="", alias="AI_MODEL_BASE_URL")
    ai_model_name: str = Field(default="", alias="AI_MODEL_NAME")
    ai_model_timeout_seconds: float = Field(default=30.0, alias="AI_MODEL_TIMEOUT_SECONDS")
    ai_model_supports_json_mode: bool = Field(default=True, alias="AI_MODEL_SUPPORTS_JSON_MODE")
    ai_search_max_history_messages: int = Field(
        default=12,
        alias="AI_SEARCH_MAX_HISTORY_MESSAGES",
    )
    ai_agent_turn_mode: str = Field(default="dual", alias="AI_AGENT_TURN_MODE")
    ai_agent_daily_turn_limit: int = Field(default=100, alias="AI_AGENT_DAILY_TURN_LIMIT")
    ai_agent_minute_turn_limit: int = Field(default=10, alias="AI_AGENT_MINUTE_TURN_LIMIT")
    ai_agent_max_sessions: int = Field(default=20, alias="AI_AGENT_MAX_SESSIONS")
    ai_agent_max_session_turns: int = Field(default=100, alias="AI_AGENT_MAX_SESSION_TURNS")
    ai_chat_retention_days: int = Field(default=30, alias="AI_CHAT_RETENTION_DAYS")
    ai_agent_storage_soft_limit_mb: int = Field(default=0, alias="AI_AGENT_STORAGE_SOFT_LIMIT_MB")
    ai_agent_storage_disable_new_writes: bool = Field(default=False, alias="AI_AGENT_STORAGE_DISABLE_NEW_WRITES")
    ai_agent_cleanup_interval_minutes: int = Field(default=60, alias="AI_AGENT_CLEANUP_INTERVAL_MINUTES")
    ai_agent_tools_enabled: bool = Field(default=True, alias="AI_AGENT_TOOLS_ENABLED")
    ai_agent_weather_provider: str = Field(default="open_meteo", alias="AI_AGENT_WEATHER_PROVIDER")
    ai_agent_weather_timeout_seconds: float = Field(default=8.0, alias="AI_AGENT_WEATHER_TIMEOUT_SECONDS")
    ai_agent_tool_timeout_seconds: float = Field(default=8.0, alias="AI_AGENT_TOOL_TIMEOUT_SECONDS")
    amap_web_service_key: str = Field(default="", alias="AMAP_WEB_SERVICE_KEY")
    baidu_map_web_service_ak: str = Field(default="", alias="BAIDU_MAP_WEB_SERVICE_AK")
    ai_agent_poi_enabled: bool = Field(default=True, alias="AI_AGENT_POI_ENABLED")
    ai_agent_poi_primary_provider: str = Field(default="amap", alias="AI_AGENT_POI_PRIMARY_PROVIDER")
    ai_agent_poi_dual_verify_enabled: bool = Field(default=False, alias="AI_AGENT_POI_DUAL_VERIFY_ENABLED")
    ai_agent_poi_cache_ttl_days: int = Field(default=30, alias="AI_AGENT_POI_CACHE_TTL_DAYS")
    ai_agent_poi_max_results: int = Field(default=5, alias="AI_AGENT_POI_MAX_RESULTS")
    ai_agent_poi_amap_monthly_limit: int = Field(default=5000, alias="AI_AGENT_POI_AMAP_MONTHLY_LIMIT")
    ai_agent_poi_amap_qps_limit: int = Field(default=3, alias="AI_AGENT_POI_AMAP_QPS_LIMIT")
    ai_agent_poi_baidu_place_daily_limit: int = Field(default=100, alias="AI_AGENT_POI_BAIDU_PLACE_DAILY_LIMIT")
    ai_agent_poi_baidu_place_qps_limit: int = Field(default=3, alias="AI_AGENT_POI_BAIDU_PLACE_QPS_LIMIT")
    ai_agent_poi_baidu_geocode_daily_limit: int = Field(default=5000, alias="AI_AGENT_POI_BAIDU_GEOCODE_DAILY_LIMIT")
    ai_agent_poi_baidu_reverse_geocode_daily_limit: int = Field(
        default=300,
        alias="AI_AGENT_POI_BAIDU_REVERSE_GEOCODE_DAILY_LIMIT",
    )
    langgraph_checkpoint_database_url: str = Field(
        default="",
        alias="LANGGRAPH_CHECKPOINT_DATABASE_URL",
    )
    langgraph_aes_key: str = Field(default="", alias="LANGGRAPH_AES_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
