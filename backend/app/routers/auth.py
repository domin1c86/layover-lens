from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    ForgotPasswordCheckEmailRequest,
    ForgotPasswordCheckEmailResponse,
    ForgotPasswordResetRequest,
    ForgotPasswordSendCodeRequest,
    ForgotPasswordSendCodeResponse,
    ForgotPasswordVerifyCodeRequest,
    ForgotPasswordVerifyCodeResponse,
    SuccessResponse,
)
from app.services.user_service import (
    AuthenticatedUser,
    UserService,
    UserServiceError,
    get_current_user,
    get_user_service,
)

router = APIRouter(prefix="/auth")


def _raise_http(exc: UserServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/register", response_model=AuthTokenResponse)
def register(
    payload: AuthRegisterRequest,
    request: Request,
    user_service: UserService = Depends(get_user_service),
) -> AuthTokenResponse:
    try:
        return user_service.register(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            request=request,
        )
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: AuthLoginRequest,
    request: Request,
    user_service: UserService = Depends(get_user_service),
) -> AuthTokenResponse:
    try:
        return user_service.login(email=payload.email, password=payload.password, request=request)
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/logout", response_model=SuccessResponse)
def logout(
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    user_service.logout(current_user.token_hash)
    return SuccessResponse(success=True)


@router.post("/forgot-password/check-email", response_model=ForgotPasswordCheckEmailResponse)
def check_email(
    payload: ForgotPasswordCheckEmailRequest,
    user_service: UserService = Depends(get_user_service),
) -> ForgotPasswordCheckEmailResponse:
    return ForgotPasswordCheckEmailResponse(registered=user_service.check_email(payload.email))


@router.post("/forgot-password/send-code", response_model=ForgotPasswordSendCodeResponse)
def send_code(
    payload: ForgotPasswordSendCodeRequest,
    user_service: UserService = Depends(get_user_service),
) -> ForgotPasswordSendCodeResponse:
    try:
        expires_in_seconds = user_service.send_reset_code(payload.email)
        return ForgotPasswordSendCodeResponse(expires_in_seconds=expires_in_seconds)
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/forgot-password/verify-code", response_model=ForgotPasswordVerifyCodeResponse)
def verify_code(
    payload: ForgotPasswordVerifyCodeRequest,
    user_service: UserService = Depends(get_user_service),
) -> ForgotPasswordVerifyCodeResponse:
    verified, reset_token = user_service.verify_reset_code(email=payload.email, code=payload.code)
    return ForgotPasswordVerifyCodeResponse(verified=verified, reset_token=reset_token)


@router.post("/forgot-password/reset", response_model=SuccessResponse)
def reset_password(
    payload: ForgotPasswordResetRequest,
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    try:
        user_service.reset_password(reset_token=payload.reset_token, new_password=payload.new_password)
        return SuccessResponse(success=True)
    except UserServiceError as exc:
        _raise_http(exc)

