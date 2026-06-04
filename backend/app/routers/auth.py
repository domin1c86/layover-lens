from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.schemas import (
    AuthLoginRequest,
    AuthLoginResponse,
    AuthRegisterRequest,
    AuthTotpVerifyRequest,
    AuthTokenResponse,
    EmailVerificationSendRequest,
    EmailVerificationSendResponse,
    EmailVerificationVerifyRequest,
    EmailVerificationVerifyResponse,
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
    clear_auth_cookies,
    get_current_user,
    get_user_service,
    require_csrf,
    set_auth_cookies,
)

router = APIRouter(prefix="/auth")


def _raise_http(exc: UserServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/register", response_model=AuthTokenResponse)
def register(
    payload: AuthRegisterRequest,
    request: Request,
    response: Response,
    user_service: UserService = Depends(get_user_service),
) -> AuthTokenResponse:
    try:
        token_response = user_service.register(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            email_verification_token=payload.email_verification_token,
            session_duration=payload.session_duration,
            request=request,
        )
        set_auth_cookies(response, token_response.access_token, token_response.expires_at)
        return token_response
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/login", response_model=AuthLoginResponse)
def login(
    payload: AuthLoginRequest,
    request: Request,
    response: Response,
    user_service: UserService = Depends(get_user_service),
) -> AuthLoginResponse:
    try:
        token_response = user_service.login(
            email=payload.email,
            password=payload.password,
            session_duration=payload.session_duration,
            request=request,
        )
        if isinstance(token_response, AuthTokenResponse):
            set_auth_cookies(response, token_response.access_token, token_response.expires_at)
        return token_response
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/login/totp", response_model=AuthTokenResponse)
def verify_login_totp(
    payload: AuthTotpVerifyRequest,
    request: Request,
    response: Response,
    user_service: UserService = Depends(get_user_service),
) -> AuthTokenResponse:
    try:
        token_response = user_service.complete_totp_login(
            challenge_token=payload.challenge_token,
            code=payload.code,
            request=request,
        )
        set_auth_cookies(response, token_response.access_token, token_response.expires_at)
        return token_response
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/logout", response_model=SuccessResponse, dependencies=[Depends(require_csrf)])
def logout(
    response: Response,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    user_service.logout(current_user.token_hash)
    clear_auth_cookies(response)
    return SuccessResponse(success=True)


@router.post("/email-verification/send", response_model=EmailVerificationSendResponse)
def send_email_verification(
    payload: EmailVerificationSendRequest,
    user_service: UserService = Depends(get_user_service),
) -> EmailVerificationSendResponse:
    try:
        expires_in_seconds = user_service.send_email_verification_code(
            email=payload.email,
            purpose=payload.purpose,
        )
        return EmailVerificationSendResponse(expires_in_seconds=expires_in_seconds)
    except UserServiceError as exc:
        _raise_http(exc)


@router.post("/email-verification/verify", response_model=EmailVerificationVerifyResponse)
def verify_email_verification(
    payload: EmailVerificationVerifyRequest,
    user_service: UserService = Depends(get_user_service),
) -> EmailVerificationVerifyResponse:
    verified, verification_token = user_service.verify_email_verification_code(
        email=payload.email,
        code=payload.code,
        purpose=payload.purpose,
    )
    return EmailVerificationVerifyResponse(verified=verified, verification_token=verification_token)


@router.post("/forgot-password/check-email", response_model=ForgotPasswordCheckEmailResponse)
def check_email(
    payload: ForgotPasswordCheckEmailRequest,
    user_service: UserService = Depends(get_user_service),
) -> ForgotPasswordCheckEmailResponse:
    registered, verification_method = user_service.get_password_reset_method(payload.email)
    return ForgotPasswordCheckEmailResponse(
        registered=registered,
        verification_method=verification_method,
    )


@router.post("/forgot-password/send-code", response_model=ForgotPasswordSendCodeResponse)
def send_code(
    payload: ForgotPasswordSendCodeRequest,
    user_service: UserService = Depends(get_user_service),
) -> ForgotPasswordSendCodeResponse:
    try:
        expires_in_seconds, verification_method = user_service.send_reset_code(payload.email)
        return ForgotPasswordSendCodeResponse(
            expires_in_seconds=expires_in_seconds,
            verification_method=verification_method,
        )
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
