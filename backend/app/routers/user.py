from email.parser import BytesParser
from email.policy import default

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.schemas import (
    AvatarResponse,
    DeviceListResponse,
    FavoriteCreateRequest,
    FavoriteCreateResponse,
    FavoriteListResponse,
    ImportPlatformUpdateRequest,
    ImportPlatformsResponse,
    SuccessResponse,
    UserEmailUpdateRequest,
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
)

router = APIRouter(prefix="/user")


def _raise_http(exc: UserServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/profile", response_model=UserProfile)
def get_profile(current_user: AuthenticatedUser = Depends(get_current_user)) -> UserProfile:
    return current_user.user


@router.put("/profile", response_model=UserProfile)
def update_profile(
    payload: UserProfileUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    try:
        return user_service.update_profile(current_user.user.id, nickname=payload.nickname)
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/avatar", response_model=AvatarResponse)
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


@router.put("/email", response_model=UserProfile)
def update_email(
    payload: UserEmailUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserProfile:
    try:
        return user_service.update_email(
            current_user.user.id,
            new_email=payload.new_email,
            code=payload.code,
        )
    except UserServiceError as exc:
        _raise_http(exc)


@router.put("/password", response_model=SuccessResponse)
def update_password(
    payload: UserPasswordUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    try:
        user_service.update_password(
            current_user.user.id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
        return SuccessResponse(success=True)
    except UserServiceError as exc:
        _raise_http(exc)


@router.get("/preferences", response_model=UserPreferences)
def get_preferences(
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserPreferences:
    return user_service.get_preferences(current_user.user.id)


@router.put("/preferences", response_model=UserPreferences)
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


@router.put("/import-platforms", response_model=ImportPlatformsResponse)
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


@router.delete("/devices/{device_id}", response_model=SuccessResponse)
def revoke_device(
    device_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    try:
        user_service.revoke_device(current_user.user.id, device_id, current_user.token_hash)
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


@router.post("/favorites", response_model=FavoriteCreateResponse)
def add_favorite(
    payload: FavoriteCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> FavoriteCreateResponse:
    try:
        return user_service.add_favorite(current_user.user.id, payload.route)
    except UserServiceError as exc:
        _raise_http(exc)


@router.delete("/favorites/{route_id}", response_model=SuccessResponse)
def delete_favorite(
    route_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    user_service.delete_favorite(current_user.user.id, route_id)
    return SuccessResponse(success=True)
