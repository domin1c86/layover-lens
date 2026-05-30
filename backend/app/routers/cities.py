from fastapi import APIRouter, Depends, Query

from app.schemas import CityListResponse
from app.services import SearchService, get_search_service

router = APIRouter()


@router.get("/cities", response_model=CityListResponse)
def get_cities(
    keyword: str = Query(default=None, description="按城市名、英文名或代码过滤"),
    search_service: SearchService = Depends(get_search_service),
) -> CityListResponse:
    return CityListResponse(cities=search_service.list_cities(keyword))
