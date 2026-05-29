from fastapi import APIRouter, Depends, HTTPException

from app.schemas import (
    AISearchResponse,
    AISearchSessionConfirmRequest,
    AISearchSessionCreateRequest,
    AISearchSessionTurnRequest,
    SearchRequest,
    SearchResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from app.services import SearchService, get_search_service
from app.services.ai_agent import AIClientError
from app.services.summarizer import summarize_message

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
) -> AISearchResponse:
    try:
        return search_service.create_ai_session(request.message)
    except AIClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
) -> AISearchResponse:
    try:
        return search_service.append_ai_message(session_id, request.message, language=request.language)
    except AIClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/search/ai/sessions/{session_id}/confirm", response_model=AISearchResponse)
def confirm_ai_search_session(
    session_id: str,
    request: AISearchSessionConfirmRequest,
    search_service: SearchService = Depends(get_search_service),
) -> AISearchResponse:
    try:
        return search_service.confirm_ai_session(session_id, confirmed=request.confirmed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/search/ai/summarize", response_model=SummarizeResponse)
def summarize_ai_message(request: SummarizeRequest) -> SummarizeResponse:
    """Generate a short conversation title from a user's travel query.

    Uses a lightweight rule-based algorithm (no LLM call).
    """
    title = summarize_message(request.message, language=request.language)
    return SummarizeResponse(title=title)
