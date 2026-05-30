from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.schemas import (
    AISearchResponse,
    AISessionListResponse,
    AISessionSummary,
    AISessionUpdateRequest,
    AISearchSessionConfirmRequest,
    AISearchSessionCreateRequest,
    AISearchSessionTurnRequest,
    SearchRequest,
    SearchResponse,
    SuccessResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from app.services import SearchService, get_search_service
from app.services.ai_agent import AIClientError
from app.services.summarizer import summarize_message
from app.services.user_service import (
    AuthenticatedUser,
    UserService,
    UserServiceError,
    get_current_user,
    get_optional_user,
    get_user_service,
)

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search_routes(
    request: SearchRequest,
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    try:
        return search_service.search(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/search/ai/sessions", response_model=AISearchResponse)
def create_ai_search_session(
    request: AISearchSessionCreateRequest,
    search_service: SearchService = Depends(get_search_service),
    user_service: UserService = Depends(get_user_service),
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user),
) -> AISearchResponse:
    try:
        response = search_service.create_ai_session(request.message)
        if current_user is not None:
            user_service.save_ai_session(
                current_user.user.id,
                response,
                title=summarize_message(request.message),
            )
        return response
    except AIClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/search/ai/sessions", response_model=AISessionListResponse)
def list_ai_search_sessions(
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> AISessionListResponse:
    return AISessionListResponse(sessions=user_service.list_ai_sessions(current_user.user.id))


@router.get("/search/ai/sessions/{session_id}", response_model=AISearchResponse)
def get_ai_search_session(
    session_id: str,
    search_service: SearchService = Depends(get_search_service),
) -> AISearchResponse:
    try:
        return search_service.get_ai_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/search/ai/sessions/{session_id}/messages", response_model=AISearchResponse)
def append_ai_search_message(
    session_id: str,
    request: AISearchSessionTurnRequest,
    search_service: SearchService = Depends(get_search_service),
    user_service: UserService = Depends(get_user_service),
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user),
) -> AISearchResponse:
    try:
        response = search_service.append_ai_message(session_id, request.message, language=request.language)
        if current_user is not None:
            user_service.save_ai_session(current_user.user.id, response)
        return response
    except AIClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/search/ai/sessions/{session_id}/confirm", response_model=AISearchResponse)
def confirm_ai_search_session(
    session_id: str,
    request: AISearchSessionConfirmRequest,
    search_service: SearchService = Depends(get_search_service),
    user_service: UserService = Depends(get_user_service),
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user),
) -> AISearchResponse:
    try:
        response = search_service.confirm_ai_session(session_id, confirmed=request.confirmed)
        if current_user is not None:
            user_service.save_ai_session(current_user.user.id, response)
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/search/ai/sessions/{session_id}", response_model=AISessionSummary)
def rename_ai_search_session(
    session_id: str,
    request: AISessionUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> AISessionSummary:
    try:
        return user_service.rename_ai_session(current_user.user.id, session_id, request.title)
    except UserServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete("/search/ai/sessions/{session_id}", response_model=SuccessResponse)
def delete_ai_search_session(
    session_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    user_service.delete_ai_session(current_user.user.id, session_id)
    return SuccessResponse(success=True)


@router.post("/search/ai/summarize", response_model=SummarizeResponse)
def summarize_ai_message(request: SummarizeRequest) -> SummarizeResponse:
    """Generate a short conversation title from a user's travel query.

    Uses a lightweight rule-based algorithm (no LLM call).
    """
    title = summarize_message(request.message, language=request.language)
    return SummarizeResponse(title=title)
