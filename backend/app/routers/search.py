from __future__ import annotations

import json
from typing import Callable, Iterator, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.schemas import (
    AISearchResponse,
    AISearchSessionConfirmRequest,
    AISearchSessionCreateRequest,
    AISearchSessionTurnRequest,
    AISessionListResponse,
    AISessionSummary,
    AISessionUpdateRequest,
    RouteFeedbackAnnotationRequest,
    RouteFeedbackAnnotationResponse,
    RouteFeedbackCreateRequest,
    RouteFeedbackResponse,
    SearchRequest,
    SearchResponse,
    SuccessResponse,
    SummarizeRequest,
    SummarizeResponse,
)
from app.services import SearchService, get_search_service
from app.agents.ai_agent import AIClientError
from app.agents.search_agent import (
    SearchAgentService,
    get_search_agent_service,
    new_ai_session_id,
)
from app.services.summarizer import summarize_message
from app.services.route_feedback import (
    RouteFeedbackError,
    RouteFeedbackService,
    get_route_feedback_service,
)
from app.services.user_service import (
    AuthenticatedUser,
    UserService,
    UserServiceError,
    get_current_user,
    get_optional_user,
    get_user_service,
    require_csrf,
)

router = APIRouter()


def _raise_user_error(exc: UserServiceError) -> None:
    detail = {"message": str(exc), "code": exc.code} if exc.code else str(exc)
    raise HTTPException(status_code=exc.status_code, detail=detail) from exc


def _run_owned_session(
    *,
    user_id: str,
    session_id: str,
    request_id: str,
    run: Callable[[], AISearchResponse],
    agent_service: SearchAgentService,
    user_service: UserService,
) -> AISearchResponse:
    user_service.assert_ai_session_owner(user_id, session_id)
    if not user_service.reserve_ai_request(user_id, session_id, request_id):
        return agent_service.get_session(session_id)
    user_service.check_ai_storage_available()
    current = agent_service.get_session(session_id)
    if current.status.value == "blocked":
        raise UserServiceError("AI session is blocked.", 409)
    if sum(1 for item in current.conversation if item.role == "user") >= settings.ai_agent_max_session_turns:
        raise UserServiceError("AI session turn limit reached.", 409)
    user_service.check_ai_agent_quota(user_id)
    run_id = f"run_{uuid4().hex}"
    user_service.acquire_ai_session_run(user_id, session_id, run_id)
    try:
        response = run()
        user_service.save_ai_session(user_id, response)
        return response
    finally:
        user_service.release_ai_session_run(user_id, session_id, run_id)


def _sse_response(
    response: AISearchResponse,
    *,
    agent_service: Optional[SearchAgentService] = None,
    language: str = "zh",
    on_done: Optional[Callable[[AISearchResponse], None]] = None,
) -> StreamingResponse:
    def generate() -> Iterator[str]:
        sequence = 0

        def event(event_name: str, payload: dict) -> str:
            nonlocal sequence
            sequence += 1
            body = {"sequence": sequence, **payload}
            return f"event: {event_name}\ndata: {json.dumps(body, ensure_ascii=False)}\n\n"

        yield event("status", {"status": response.status.value})
        for tool_result in response.tool_results:
            yield event("tool_result", {"tool_result": tool_result.model_dump(mode="json")})
        final_response = response
        if response.pending_reply and agent_service is not None:
            chunks = []
            try:
                for chunk in agent_service.stream_reply_chunks(response, language=language):
                    if not chunk:
                        continue
                    chunks.append(chunk)
                    yield event("assistant_delta", {"delta": chunk})
                final_response = agent_service.complete_streaming_reply(response.session_id, "".join(chunks).strip())
                if on_done:
                    on_done(final_response)
            except AIClientError as exc:
                yield event("error", {"message": str(exc), "code": "ai_stream_failed"})
                final_response = agent_service.complete_streaming_reply(
                    response.session_id,
                    "AI response generation failed. Please try again.",
                )
                if on_done:
                    on_done(final_response)
        else:
            text = response.assistant_message
            for start in range(0, len(text), 8):
                yield event("assistant_delta", {"delta": text[start:start + 8]})
        if final_response.search_response is not None:
            yield event("search_result", {"search_response": final_response.search_response.model_dump(mode="json")})
        yield event("done", {"response": final_response.model_dump(mode="json")})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


def _cleanup_user_checkpoints(
    user_id: str,
    agent_service: SearchAgentService,
    user_service: UserService,
) -> None:
    for session_id in user_service.list_expired_ai_session_ids(user_id):
        try:
            agent_service.delete_session(session_id)
        except Exception as exc:
            user_service.queue_ai_checkpoint_deletion(user_id, session_id, str(exc))
        user_service.delete_ai_session(user_id, session_id)
    for session_id in user_service.list_pending_ai_checkpoint_deletions(user_id):
        try:
            agent_service.delete_session(session_id)
            user_service.complete_ai_checkpoint_deletion(session_id)
        except Exception:
            continue


@router.post("/search", response_model=SearchResponse)
def search_routes(
    request: SearchRequest,
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    try:
        return search_service.search(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/search/feedback",
    response_model=RouteFeedbackResponse,
    dependencies=[Depends(require_csrf)],
)
def create_route_feedback(
    request: RouteFeedbackCreateRequest,
    current_user: Optional[AuthenticatedUser] = Depends(get_optional_user),
    feedback_service: RouteFeedbackService = Depends(get_route_feedback_service),
) -> RouteFeedbackResponse:
    try:
        user_id = current_user.user.id if current_user is not None else None
        return feedback_service.create_feedback(user_id, request)
    except RouteFeedbackError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put(
    "/search/feedback/{feedback_id}/annotation",
    response_model=RouteFeedbackAnnotationResponse,
    dependencies=[Depends(require_csrf)],
)
def annotate_route_feedback(
    feedback_id: str,
    request: RouteFeedbackAnnotationRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    feedback_service: RouteFeedbackService = Depends(get_route_feedback_service),
) -> RouteFeedbackAnnotationResponse:
    try:
        return feedback_service.annotate_feedback(feedback_id, current_user.user.id, request)
    except RouteFeedbackError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/search/feedback/annotated")
def export_route_feedback_annotations(
    _: AuthenticatedUser = Depends(get_current_user),
    feedback_service: RouteFeedbackService = Depends(get_route_feedback_service),
) -> dict:
    samples = feedback_service.export_annotated_samples()
    return {"samples": samples, "total": len(samples)}


def _create_ai_session(
    request: AISearchSessionCreateRequest,
    current_user: AuthenticatedUser,
    agent_service: SearchAgentService,
    user_service: UserService,
    *,
    stream_reply: bool = False,
) -> AISearchResponse:
    try:
        _cleanup_user_checkpoints(current_user.user.id, agent_service, user_service)
        user_service.check_ai_storage_available()
        user_service.check_ai_session_capacity(current_user.user.id)
        user_service.check_ai_agent_quota(current_user.user.id)
        session_id = new_ai_session_id()
        request_id = request.request_id or f"req_{uuid4().hex}"
        response = agent_service.create_session(
            session_id=session_id,
            user_id=current_user.user.id,
            message=request.message,
            language=request.language or "zh",
            stream_reply=stream_reply,
            request_id=request_id,
        )
        try:
            user_service.save_ai_session(
                current_user.user.id,
                response,
                title=summarize_message(request.message, language=request.language or "zh"),
            )
        except Exception:
            agent_service.delete_session(session_id)
            raise
        if request.request_id:
            user_service.reserve_ai_request(current_user.user.id, session_id, request_id)
        return response
    except UserServiceError as exc:
        _raise_user_error(exc)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AIClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/search/ai/sessions",
    response_model=AISearchResponse,
    dependencies=[Depends(require_csrf)],
)
def create_ai_search_session(
    request: AISearchSessionCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    agent_service: SearchAgentService = Depends(get_search_agent_service),
    user_service: UserService = Depends(get_user_service),
) -> AISearchResponse:
    return _create_ai_session(request, current_user, agent_service, user_service)


@router.post("/search/ai/sessions/stream", dependencies=[Depends(require_csrf)])
def create_ai_search_session_stream(
    request: AISearchSessionCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    agent_service: SearchAgentService = Depends(get_search_agent_service),
    user_service: UserService = Depends(get_user_service),
) -> StreamingResponse:
    response = _create_ai_session(request, current_user, agent_service, user_service, stream_reply=True)
    return _sse_response(
        response,
        agent_service=agent_service,
        language=request.language or "zh",
        on_done=lambda final_response: user_service.save_ai_session(current_user.user.id, final_response),
    )


@router.get("/search/ai/sessions", response_model=AISessionListResponse)
def list_ai_search_sessions(
    current_user: AuthenticatedUser = Depends(get_current_user),
    agent_service: SearchAgentService = Depends(get_search_agent_service),
    user_service: UserService = Depends(get_user_service),
) -> AISessionListResponse:
    _cleanup_user_checkpoints(current_user.user.id, agent_service, user_service)
    return AISessionListResponse(sessions=user_service.list_ai_sessions(current_user.user.id))


@router.get("/search/ai/sessions/{session_id}", response_model=AISearchResponse)
def get_ai_search_session(
    session_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    agent_service: SearchAgentService = Depends(get_search_agent_service),
    user_service: UserService = Depends(get_user_service),
) -> AISearchResponse:
    try:
        user_service.assert_ai_session_owner(current_user.user.id, session_id)
        return agent_service.get_session(session_id)
    except UserServiceError as exc:
        _raise_user_error(exc)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _append_ai_message(
    session_id: str,
    request: AISearchSessionTurnRequest,
    current_user: AuthenticatedUser,
    agent_service: SearchAgentService,
    user_service: UserService,
    *,
    stream_reply: bool = False,
) -> AISearchResponse:
    try:
        request_id = request.request_id or f"req_{uuid4().hex}"
        return _run_owned_session(
            user_id=current_user.user.id,
            session_id=session_id,
            request_id=request_id,
            run=lambda: agent_service.append_message(
                session_id,
                message=request.message,
                language=request.language or "zh",
                stream_reply=stream_reply,
                request_id=request_id,
            ),
            agent_service=agent_service,
            user_service=user_service,
        )
    except UserServiceError as exc:
        _raise_user_error(exc)
    except AIClientError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post(
    "/search/ai/sessions/{session_id}/messages",
    response_model=AISearchResponse,
    dependencies=[Depends(require_csrf)],
)
def append_ai_search_message(
    session_id: str,
    request: AISearchSessionTurnRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    agent_service: SearchAgentService = Depends(get_search_agent_service),
    user_service: UserService = Depends(get_user_service),
) -> AISearchResponse:
    return _append_ai_message(session_id, request, current_user, agent_service, user_service)


@router.post("/search/ai/sessions/{session_id}/messages/stream", dependencies=[Depends(require_csrf)])
def append_ai_search_message_stream(
    session_id: str,
    request: AISearchSessionTurnRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    agent_service: SearchAgentService = Depends(get_search_agent_service),
    user_service: UserService = Depends(get_user_service),
) -> StreamingResponse:
    response = _append_ai_message(
        session_id,
        request,
        current_user,
        agent_service,
        user_service,
        stream_reply=True,
    )
    return _sse_response(
        response,
        agent_service=agent_service,
        language=request.language or "zh",
        on_done=lambda final_response: user_service.save_ai_session(current_user.user.id, final_response),
    )


def _confirm_ai_session(
    session_id: str,
    request: AISearchSessionConfirmRequest,
    current_user: AuthenticatedUser,
    agent_service: SearchAgentService,
    user_service: UserService,
    *,
    stream_reply: bool = False,
) -> AISearchResponse:
    try:
        request_id = request.request_id or f"req_{uuid4().hex}"
        return _run_owned_session(
            user_id=current_user.user.id,
            session_id=session_id,
            request_id=request_id,
            run=lambda: agent_service.confirm(
                session_id,
                confirmed=request.confirmed,
                language=request.language or "zh",
                stream_reply=stream_reply,
                request_id=request_id,
            ),
            agent_service=agent_service,
            user_service=user_service,
        )
    except UserServiceError as exc:
        _raise_user_error(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/search/ai/sessions/{session_id}/confirm",
    response_model=AISearchResponse,
    dependencies=[Depends(require_csrf)],
)
def confirm_ai_search_session(
    session_id: str,
    request: AISearchSessionConfirmRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    agent_service: SearchAgentService = Depends(get_search_agent_service),
    user_service: UserService = Depends(get_user_service),
) -> AISearchResponse:
    return _confirm_ai_session(session_id, request, current_user, agent_service, user_service)


@router.post("/search/ai/sessions/{session_id}/confirm/stream", dependencies=[Depends(require_csrf)])
def confirm_ai_search_session_stream(
    session_id: str,
    request: AISearchSessionConfirmRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    agent_service: SearchAgentService = Depends(get_search_agent_service),
    user_service: UserService = Depends(get_user_service),
) -> StreamingResponse:
    response = _confirm_ai_session(
        session_id,
        request,
        current_user,
        agent_service,
        user_service,
        stream_reply=True,
    )
    return _sse_response(
        response,
        agent_service=agent_service,
        language=request.language or "zh",
        on_done=lambda final_response: user_service.save_ai_session(current_user.user.id, final_response),
    )


@router.put("/search/ai/sessions/{session_id}", response_model=AISessionSummary, dependencies=[Depends(require_csrf)])
def rename_ai_search_session(
    session_id: str,
    request: AISessionUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> AISessionSummary:
    try:
        return user_service.rename_ai_session(current_user.user.id, session_id, request.title)
    except UserServiceError as exc:
        _raise_user_error(exc)


@router.delete("/search/ai/sessions/{session_id}", response_model=SuccessResponse, dependencies=[Depends(require_csrf)])
def delete_ai_search_session(
    session_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    agent_service: SearchAgentService = Depends(get_search_agent_service),
    user_service: UserService = Depends(get_user_service),
) -> SuccessResponse:
    try:
        user_service.assert_ai_session_owner(current_user.user.id, session_id)
        try:
            agent_service.delete_session(session_id)
        except Exception as exc:
            user_service.queue_ai_checkpoint_deletion(current_user.user.id, session_id, str(exc))
        user_service.delete_ai_session(current_user.user.id, session_id)
        return SuccessResponse(success=True)
    except UserServiceError as exc:
        _raise_user_error(exc)


@router.post("/search/ai/summarize", response_model=SummarizeResponse, dependencies=[Depends(require_csrf)])
def summarize_ai_message(
    request: SummarizeRequest,
    _: AuthenticatedUser = Depends(get_current_user),
) -> SummarizeResponse:
    return SummarizeResponse(title=summarize_message(request.message, language=request.language))
