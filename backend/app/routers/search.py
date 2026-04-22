from fastapi import APIRouter, Depends, HTTPException

from app.schemas import SearchRequest, SearchResponse
from app.services import SearchService, get_search_service

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
