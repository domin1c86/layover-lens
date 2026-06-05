from email.parser import BytesParser
from email.policy import default

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.config import settings
from app.schemas import (
    AvatarPresetUpdateRequest,
    AvatarResponse,
    DeviceListResponse,
    FavoriteCreateRequest,
    FavoriteCreateResponse,
    FavoriteListResponse,
    ImportPlatformUpdateRequest,
    ImportPlatformsResponse,
    SessionDurationUpdateRequest,
    SessionDurationUpdateResponse,
    SuccessResponse,
    TotpDisableRequest,
    TotpEmailCodeReplacementUpdateRequest,
    TotpEnableRequest,
    TotpSetupRequest,
    TotpSetupResponse,
    UserEmailUpdateRequest,
    UserEmailVerifyRequest,
    UserPasswordCheckRequest,
    UserPasswordCheckResponse,
    UserPasswordUpdateRequest,
    UserPreferences,
    UserPreferencesUpdate,
    UserProfile,
    UserProfileUpdate,
)
from app.services.user_service import (
    AuthenticatedUser,
    UserService,
    UserServiceError,
    get_current_user,
    get_user_service,
    require_csrf,
    set_auth_cookies,
)
from app.agents.search_agent import SearchAgentService, get_search_agent_service

router = APIRouter(prefix="/user")


def _raise_http(exc: UserServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/profile", response_model=UserProfile)
def get_profile(current_user: AuthenticatedUser = Depends(get_current_user)) -> UserProfile:
    return current_user.user


@router.put("/profile", response_model=UserProfile, dependencies=[Depends(require_csrf)])
def update_profile(
    payload: UserProfileUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    try:
        return user_service.update_profile(current_user.user.id, nickname=payload.nickname)
    except UserServiceError as exc:
        _raise_http(exc)


@router.delete("/account", response_model=SuccessResponse, dependencies=[Depends(require_csrf)])
def delete_account(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    agent_service: SearchAgentService = Depends(get_search_agent_service),
) -> SuccessResponse:
    try:
        ai_session_ids = user_service.list_user_ai_session_ids(current_user.user.id)
        user_service.delete_account(current_user.user.id, request=request)
        for session_id in ai_session_ids:
            try:
                agent_service.delete_session(session_id)
            except Exception as exc:
                user_service.queue_ai_checkpoint_deletion(current_user.user.id, session_id, str(exc))
        return SuccessResponse(success=True)
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/avatar", response_model=AvatarResponse, dependencies=[Depends(require_csrf)])
async def upload_avatar(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> AvatarResponse:
    content_type = request.headers.get("content-type", "application/octet-stream")
    data = await request.body()
    if content_type.startswith("multipart/form-data"):
        data, content_type = _extract_multipart_file(data, content_type)
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Avatar must be an image.")
    if not data:
        raise HTTPException(status_code=400, detail="Avatar file is empty.")
    try:
        avatar_url = user_service.update_avatar(
            current_user.user.id,
            content_type=content_type,
            data=data,
        )
        return AvatarResponse(avatar_url=avatar_url)
    except UserServiceError as exc:
        _raise_http(exc)


@router.put("/avatar/preset", response_model=UserProfile, dependencies=[Depends(require_csrf)])
def update_avatar_preset(
    payload: AvatarPresetUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    try:
        return user_service.update_avatar_preset(
            current_user.user.id,
            preset_id=payload.preset_id,
        )
    except UserServiceError as exc:
        _raise_http(exc)


def _extract_multipart_file(body: bytes, content_type: str) -> tuple[bytes, str]:
    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: " + content_type.encode("utf-8") + b"\r\n\r\n" + body
    )
    for part in message.iter_parts():
        disposition = part.get("Content-Disposition", "")
        if "name=\"file\"" not in disposition:
            continue
        payload = part.get_payload(decode=True) or b""
        part_content_type = part.get_content_type() or "application/octet-stream"
        return payload, part_content_type
    raise HTTPException(status_code=400, detail="Multipart request must include a file field.")


@router.get("/avatar/{user_id}")
def get_avatar(
    user_id: str,
    user_service: UserService = Depends(get_user_service),
) -> Response:
    try:
        content_type, data = user_service.get_avatar(user_id)
        return Response(content=data, media_type=content_type)
    except UserServiceError as exc:
        _raise_http(exc)


@router.put("/email", response_model=UserProfile, dependencies=[Depends(require_csrf)])
def update_email(
    payload: UserEmailUpdateRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    try:
        return user_service.update_email(
            current_user.user.id,
            new_email=payload.new_email,
            current_email=payload.current_email,
            verification_token=payload.verification_token,
            request=request,
        )
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/email/verify", response_model=UserProfile, dependencies=[Depends(require_csrf)])
def verify_email(
    payload: UserEmailVerifyRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    try:
        return user_service.verify_current_email(
            current_user.user.id,
            verification_token=payload.verification_token,
        )
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/password/check", response_model=UserPasswordCheckResponse, dependencies=[Depends(require_csrf)])
def check_password(
    payload: UserPasswordCheckRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserPasswordCheckResponse:
    return UserPasswordCheckResponse(
        valid=user_service.check_password(current_user.user.id, payload.current_password)
    )


@router.put("/password", response_model=SuccessResponse, dependencies=[Depends(require_csrf)])
def update_password(
    payload: UserPasswordUpdateRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    try:
        user_service.update_password(
            current_user.user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
            request=request,
        )
        user_service.revoke_other_tokens(current_user.user.id, current_user.token_hash)
        return SuccessResponse(success=True)
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/totp/setup", response_model=TotpSetupResponse, dependencies=[Depends(require_csrf)])
def setup_totp(
    payload: TotpSetupRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> TotpSetupResponse:
    try:
        return user_service.begin_totp_setup(
            current_user.user.id,
            current_password=payload.current_password,
            request=request,
        )
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/totp/enable", response_model=UserProfile, dependencies=[Depends(require_csrf)])
def enable_totp(
    payload: TotpEnableRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    try:
        profile = user_service.enable_totp(
            current_user.user.id,
            code=payload.code,
            request=request,
        )
        user_service.revoke_other_tokens(current_user.user.id, current_user.token_hash)
        return profile
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/totp/disable", response_model=UserProfile, dependencies=[Depends(require_csrf)])
def disable_totp(
    payload: TotpDisableRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    try:
        profile = user_service.disable_totp(
            current_user.user.id,
            current_password=payload.current_password,
            code=payload.code,
            request=request,
        )
        user_service.revoke_other_tokens(current_user.user.id, current_user.token_hash)
        return profile
    except UserServiceError as exc:
        _raise_http(exc)


@router.put("/totp/email-code-replacement", response_model=UserProfile, dependencies=[Depends(require_csrf)])
def update_totp_email_code_replacement(
    payload: TotpEmailCodeReplacementUpdateRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    try:
        return user_service.update_totp_email_code_replacement(
            current_user.user.id,
            enabled=payload.enabled,
            request=request,
        )
    except UserServiceError as exc:
        _raise_http(exc)


@router.put("/session-duration", response_model=SessionDurationUpdateResponse, dependencies=[Depends(require_csrf)])
def update_session_duration(
    payload: SessionDurationUpdateRequest,
    request: Request,
    response: Response,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> SessionDurationUpdateResponse:
    try:
        expires_at = user_service.update_current_session_duration(
            current_user.user.id,
            current_user.token_hash,
            payload.session_duration,
        )
        session_token = request.cookies.get(settings.auth_cookie_name)
        if session_token:
            set_auth_cookies(response, session_token, expires_at)
        return SessionDurationUpdateResponse(
            expires_at=expires_at,
            session_duration=payload.session_duration,
        )
    except UserServiceError as exc:
        _raise_http(exc)


@router.get("/preferences", response_model=UserPreferences)
def get_preferences(
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserPreferences:
    return user_service.get_preferences(current_user.user.id)


@router.put("/preferences", response_model=UserPreferences, dependencies=[Depends(require_csrf)])
def update_preferences(
    payload: UserPreferencesUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserPreferences:
    return user_service.update_preferences(current_user.user.id, payload)


@router.get("/import-platforms", response_model=ImportPlatformsResponse)
def get_import_platforms(
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ImportPlatformsResponse:
    return ImportPlatformsResponse(platforms=user_service.get_import_platforms(current_user.user.id))


@router.put("/import-platforms", response_model=ImportPlatformsResponse, dependencies=[Depends(require_csrf)])
def update_import_platforms(
    payload: ImportPlatformUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> ImportPlatformsResponse:
    platforms = user_service.update_import_platform(
        current_user.user.id,
        payload.platform_key,
        payload.enabled,
    )
    return ImportPlatformsResponse(platforms=platforms)


@router.get("/devices", response_model=DeviceListResponse)
def list_devices(
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> DeviceListResponse:
    return DeviceListResponse(
        devices=user_service.list_devices(current_user.user.id, current_user.token_hash)
    )


@router.delete("/devices/{device_id}", response_model=SuccessResponse, dependencies=[Depends(require_csrf)])
def revoke_device(
    device_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    try:
        user_service.revoke_device(current_user.user.id, device_id, current_user.token_hash, request=request)
        return SuccessResponse(success=True)
    except UserServiceError as exc:
        _raise_http(exc)


@router.get("/favorites", response_model=FavoriteListResponse)
def list_favorites(
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> FavoriteListResponse:
    favorites = user_service.list_favorites(current_user.user.id)
    return FavoriteListResponse(favorites=favorites, total=len(favorites))


@router.post("/favorites", response_model=FavoriteCreateResponse, dependencies=[Depends(require_csrf)])
def add_favorite(
    payload: FavoriteCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> FavoriteCreateResponse:
    try:
        return user_service.add_favorite(current_user.user.id, payload.route)
    except UserServiceError as exc:
        _raise_http(exc)


@router.delete("/favorites/{route_id}", response_model=SuccessResponse, dependencies=[Depends(require_csrf)])
def delete_favorite(
    route_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    user_service.delete_favorite(current_user.user.id, route_id)
    return SuccessResponse(success=True)
