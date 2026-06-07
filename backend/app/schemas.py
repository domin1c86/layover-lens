from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class TransportType(str, Enum):
    FLIGHT = "flight"
    TRAIN = "train"


class OptimizationTarget(str, Enum):
    PRICE = "price"
    TIME = "time"
    TRANSFER = "transfer"
    BALANCED = "balanced"


class City(BaseModel):
    code: str
    name: str
    name_en: str = ""
    country: str = "中国"


class CityListResponse(BaseModel):
    cities: list[City]


class TimeRange(BaseModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")

    @field_validator("start", "end")
    @classmethod
    def validate_clock_value(cls, value: str) -> str:
        hours, minutes = [int(part) for part in value.split(":")]
        if hours not in range(24) or minutes not in range(60):
            raise ValueError("Time values must be valid 24-hour clocks.")
        return value


class Leg(BaseModel):
    transport_type: TransportType
    from_city: str
    to_city: str
    from_city_en: str = ""
    to_city_en: str = ""
    from_station: str
    to_station: str
    from_station_en: str = ""
    to_station_en: str = ""
    departure_date: str
    departure_time: str
    arrival_date: str
    arrival_time: str
    duration_minutes: int
    price: float
    company: str
    flight_train_no: str
    platform: str = ""


class RoutePlan(BaseModel):
    id: str
    total_price: float
    total_duration_minutes: int
    transfer_count: int
    legs: list[Leg]
    score: Optional[float] = None
    tag: Optional[str] = None


class SegmentAvailability(BaseModel):
    from_city_code: str
    to_city_code: str
    transport_type: TransportType
    sample_count: int
    estimated_price: float
    estimated_duration_minutes: int
    service_frequency_score: float
    availability_score: float
    confidence: float
    price_stability_score: float = 1.0
    duration_stability_score: float = 1.0
    data_source: str


class RecommendationSegment(BaseModel):
    from_city: str
    to_city: str
    from_city_en: str = ""
    to_city_en: str = ""
    recommended_transport_type: TransportType
    available_transport_types: list[TransportType]
    estimated_price: float
    estimated_duration_minutes: int
    estimated_price_level: Literal["low", "medium", "high"]
    estimated_duration_level: Literal["short", "medium", "long"]
    service_frequency_level: Literal["low", "medium", "high"]
    availability: SegmentAvailability
    data_source: str


class RouteRecommendation(BaseModel):
    id: str
    city_path: list[str]
    city_path_en: list[str]
    transfer_cities: list[str]
    transfer_cities_en: list[str]
    segments: list[RecommendationSegment]
    estimated_total_price: float
    estimated_total_duration_minutes: int
    estimated_price_level: Literal["low", "medium", "high"]
    estimated_duration_level: Literal["short", "medium", "long"]
    transfer_count: int
    score: float
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_city: str
    to_city: str
    travel_date: date = Field(
        validation_alias=AliasChoices("travel_date", "date"),
    )
    optimization_target: OptimizationTarget = Field(
        default=OptimizationTarget.BALANCED,
        validation_alias=AliasChoices("optimization_target", "optimize"),
    )
    max_transfers: Optional[int] = Field(default=None, ge=0, le=4)
    min_transfers: Optional[int] = Field(default=None, ge=0, le=4)
    preferred_transport_types: Optional[list[TransportType]] = None
    max_price: Optional[float] = Field(default=None, ge=0)
    max_total_duration_minutes: Optional[int] = Field(default=None, ge=1)
    excluded_cities: list[str] = Field(default_factory=list)
    required_transfer_cities: list[str] = Field(default_factory=list)
    departure_time_range: Optional[TimeRange] = None
    arrival_time_range: Optional[TimeRange] = None
    allow_overnight: bool = True

    @model_validator(mode="before")
    @classmethod
    def extract_legacy_filters(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        filters = payload.get("filters")
        if isinstance(filters, dict):
            legacy_mapping = {
                "max_transfer": "max_transfers",
                "max_price": "max_price",
                "max_total_duration_minutes": "max_total_duration_minutes",
                "preferred_transport_types": "preferred_transport_types",
                "transport_types": "preferred_transport_types",
                "excluded_cities": "excluded_cities",
                "required_transfer_cities": "required_transfer_cities",
                "departure_time_range": "departure_time_range",
                "arrival_time_range": "arrival_time_range",
                "allow_overnight": "allow_overnight",
            }
            for legacy_key, normalized_key in legacy_mapping.items():
                if legacy_key in filters and normalized_key not in payload:
                    payload[normalized_key] = filters[legacy_key]
        return payload


class SearchResponse(BaseModel):
    search_id: str
    routes: list[RoutePlan]
    result_mode: Literal["strategy", "legacy_detail"] = "strategy"
    recommendations: list[RouteRecommendation] = Field(default_factory=list)
    strategy_notice: Optional[str] = None
    total_count: int
    total: int
    data_mode: Literal["mock", "historical"] = "mock"
    data_notice: Optional[str] = None
    mock_source_date: Optional[str] = None
    route_dataset_mode: Optional[str] = None
    route_dataset_version: Optional[str] = None
    route_model_version: Optional[str] = None


class ParsedSearchRequest(BaseModel):
    from_city: Optional[str] = None
    to_city: Optional[str] = None
    travel_date: Optional[date] = None
    optimization_target: Optional[OptimizationTarget] = None
    max_transfers: Optional[int] = None
    preferred_transport_types: Optional[list[TransportType]] = None
    max_price: Optional[float] = None
    max_total_duration_minutes: Optional[int] = None
    excluded_cities: list[str] = Field(default_factory=list)
    required_transfer_cities: list[str] = Field(default_factory=list)
    departure_time_range: Optional[TimeRange] = None
    arrival_time_range: Optional[TimeRange] = None
    allow_overnight: Optional[bool] = None


class AIToolResult(BaseModel):
    name: str
    status: Literal["success", "error"] = "success"
    content: str
    data: dict = Field(default_factory=dict)


class AIChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)
    search_response: Optional[SearchResponse] = None
    tool_results: list[AIToolResult] = Field(default_factory=list)


class AISearchSessionStatus(str, Enum):
    COLLECTING = "collecting"
    COLLECTING_REQUIRED = "collecting_required"
    COLLECTING_OPTIONAL = "collecting_optional"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    EXECUTING = "executing"
    RESULTS_AVAILABLE = "results_available"
    FAILED = "failed"
    COMPLETED = "completed"


class AISearchSessionCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    language: Optional[str] = Field(default="zh", pattern="^(zh|en)$")
    request_id: Optional[str] = Field(default=None, min_length=8, max_length=100)


class AISearchSessionTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    language: Optional[str] = Field(default="zh", pattern="^(zh|en)$")
    request_id: Optional[str] = Field(default=None, min_length=8, max_length=100)


class AISearchSessionConfirmRequest(BaseModel):
    confirmed: bool = True
    language: Optional[str] = Field(default="zh", pattern="^(zh|en)$")
    request_id: Optional[str] = Field(default=None, min_length=8, max_length=100)


class AISearchResponse(BaseModel):
    session_id: str
    status: AISearchSessionStatus
    assistant_message: str
    conversation: list[AIChatMessage]
    parsed_request: ParsedSearchRequest
    final_request: Optional[SearchRequest] = None
    missing_fields: list[str]
    summary: str
    ready_for_confirmation: bool
    search_executed: bool
    search_response: Optional[SearchResponse] = None
    next_question_field: Optional[str] = None
    answered_fields: list[str] = Field(default_factory=list)
    skipped_fields: list[str] = Field(default_factory=list)
    tool_results: list[AIToolResult] = Field(default_factory=list)
    pending_reply: bool = False


class SummarizeRequest(BaseModel):
    message: str
    language: str = "zh"


class SummarizeResponse(BaseModel):
    title: str


RouteFeedbackAction = Literal["shown", "selected", "favorited", "ignored", "negative"]
RouteFeedbackSource = Literal["search", "ai"]
RouteFeedbackContext = Literal["route_card", "ai_experience"]
TicketProvider = Literal["12306", "ctrip", "fliggy", "qunar"]
RouteAnnotationLabel = Literal["good", "acceptable", "bad", "invalid"]
RouteAnnotationIssue = Literal[
    "too_expensive",
    "too_slow",
    "too_many_transfers",
    "low_frequency",
    "unreliable_transfer",
    "bad_transport_mix",
    "better_direct_available",
]


class RouteFeedbackRatings(BaseModel):
    overall: int = Field(ge=1, le=5)
    route_reasonable: int = Field(ge=1, le=5)
    cost_trustworthy: int = Field(ge=1, le=5)
    transfer_clear: int = Field(ge=1, le=5)


class RouteFeedbackCreateRequest(BaseModel):
    search_id: str = Field(min_length=1, max_length=120)
    recommendation_id: str = Field(min_length=1, max_length=255)
    action: RouteFeedbackAction = "shown"
    anonymous_session_id: Optional[str] = Field(default=None, max_length=120)
    source: RouteFeedbackSource = "search"
    feedback_context: RouteFeedbackContext = "route_card"
    ratings: Optional[RouteFeedbackRatings] = None
    selected_recommendation_ids: list[str] = Field(default_factory=list)
    clicked_provider: Optional[TicketProvider] = None
    clicked_segment_index: Optional[int] = Field(default=None, ge=0)
    comment: Optional[str] = Field(default=None, max_length=2000)
    search_request: dict = Field(default_factory=dict)
    recommendation: dict = Field(default_factory=dict)
    model_version: Optional[str] = Field(default=None, max_length=120)
    dataset_version: Optional[str] = Field(default=None, max_length=120)


class RouteFeedbackResponse(BaseModel):
    id: str
    created_at: datetime


class RouteFeedbackAnnotationRequest(BaseModel):
    label: RouteAnnotationLabel
    issues: list[RouteAnnotationIssue] = Field(default_factory=list)
    notes: Optional[str] = Field(default=None, max_length=2000)


class RouteFeedbackAnnotationResponse(BaseModel):
    feedback_id: str
    label: RouteAnnotationLabel
    issues: list[RouteAnnotationIssue] = Field(default_factory=list)
    annotated_at: datetime


class UserProfile(BaseModel):
    id: str
    username: str
    email: str
    email_verified: bool = True
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    totp_enabled: bool = False
    totp_replaces_email_codes: bool = False
    created_at: datetime


SessionDuration = Literal["day", "week", "month", "half_year", "year", "forever"]


class AuthLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)
    session_duration: SessionDuration = "day"


class AuthRegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=255)
    email_verification_token: str = Field(min_length=16, max_length=255)
    session_duration: SessionDuration = "day"


class AuthTokenResponse(BaseModel):
    requires_totp: Literal[False] = False
    user: UserProfile
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: Optional[datetime] = None
    session_duration: SessionDuration = "day"


class AuthTotpChallengeResponse(BaseModel):
    requires_totp: Literal[True] = True
    challenge_token: str
    expires_in_seconds: int


AuthLoginResponse = Union[AuthTokenResponse, AuthTotpChallengeResponse]


class AuthTotpVerifyRequest(BaseModel):
    challenge_token: str = Field(min_length=16, max_length=255)
    code: str = Field(min_length=6, max_length=12)


class SessionDurationUpdateRequest(BaseModel):
    session_duration: SessionDuration


class SessionDurationUpdateResponse(BaseModel):
    expires_at: Optional[datetime] = None
    session_duration: SessionDuration


class SuccessResponse(BaseModel):
    success: bool = True


class ForgotPasswordCheckEmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class ForgotPasswordCheckEmailResponse(BaseModel):
    registered: bool
    verification_method: Literal["email", "totp"] = "email"


class ForgotPasswordSendCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class ForgotPasswordSendCodeResponse(BaseModel):
    expires_in_seconds: int
    verification_method: Literal["email", "totp"] = "email"


class ForgotPasswordVerifyCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    code: str = Field(min_length=4, max_length=12)


class ForgotPasswordVerifyCodeResponse(BaseModel):
    verified: bool
    reset_token: Optional[str] = None


class ForgotPasswordResetRequest(BaseModel):
    reset_token: str = Field(min_length=16, max_length=255)
    new_password: str = Field(min_length=6, max_length=255)


EmailVerificationPurpose = Literal["register", "verify_current", "change_email"]


class EmailVerificationSendRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    purpose: EmailVerificationPurpose


class EmailVerificationSendResponse(BaseModel):
    expires_in_seconds: int


class EmailVerificationVerifyRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    code: str = Field(min_length=4, max_length=12)
    purpose: EmailVerificationPurpose


class EmailVerificationVerifyResponse(BaseModel):
    verified: bool
    verification_token: Optional[str] = None


class UserProfileUpdate(BaseModel):
    nickname: Optional[str] = Field(default=None, max_length=80)


class AvatarResponse(BaseModel):
    avatar_url: str


class AvatarPresetUpdateRequest(BaseModel):
    preset_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")


class UserEmailUpdateRequest(BaseModel):
    new_email: str = Field(min_length=3, max_length=255)
    current_email: str = Field(min_length=3, max_length=255)
    verification_token: str = Field(min_length=16, max_length=255)


class UserEmailVerifyRequest(BaseModel):
    verification_token: str = Field(min_length=16, max_length=255)


class UserPasswordCheckRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)


class UserPasswordCheckResponse(BaseModel):
    valid: bool


class UserPasswordUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=6, max_length=255)


class TotpSetupRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TotpEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class TotpDisableRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=6, max_length=12)


class TotpEmailCodeReplacementUpdateRequest(BaseModel):
    enabled: bool


class UserPreferences(BaseModel):
    theme: Literal["light", "dark"] = "light"
    language: Literal["zh", "en"] = "zh"
    search_retention_days: int = 30
    chat_retention_days: int = 30
    import_platforms: dict[str, bool] = Field(default_factory=dict)


class UserPreferencesUpdate(BaseModel):
    theme: Optional[Literal["light", "dark"]] = None
    language: Optional[Literal["zh", "en"]] = None
    search_retention_days: Optional[int] = None
    chat_retention_days: Optional[int] = None
    import_platforms: Optional[dict[str, bool]] = None


class ImportPlatformsResponse(BaseModel):
    platforms: dict[str, bool]


class ImportPlatformUpdateRequest(BaseModel):
    platform_key: str = Field(min_length=1, max_length=80)
    enabled: bool


class DeviceInfo(BaseModel):
    id: str
    device_name: str
    ip_address: str
    login_time: datetime
    is_current: bool


class DeviceListResponse(BaseModel):
    devices: list[DeviceInfo]


class FavoriteCreateRequest(BaseModel):
    route: RoutePlan


class FavoriteCreateResponse(BaseModel):
    id: str
    created_at: datetime


class FavoriteListResponse(BaseModel):
    favorites: list[RoutePlan]
    total: int


class AISessionSummary(BaseModel):
    session_id: str
    title: str
    status: AISearchSessionStatus
    last_message_preview: str
    created_at: datetime
    updated_at: datetime


class AISessionListResponse(BaseModel):
    sessions: list[AISessionSummary]


class AISessionUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class BookingCreateRequest(BaseModel):
    route_id: str = Field(min_length=1, max_length=255)
    legs: list[Leg] = Field(default_factory=list)


class BookingCreateResponse(BaseModel):
    booking_id: str
    status: str
    redirect_url: Optional[str] = None
