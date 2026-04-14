from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, time
from enum import Enum

router = APIRouter()


class TransportType(str, Enum):
    FLIGHT = "flight"
    TRAIN = "train"


class OptimizationTarget(str, Enum):
    PRICE = "price"
    TIME = "time"
    TRANSFER = "transfer"
    BALANCED = "balanced"


class Leg(BaseModel):
    transport_type: TransportType
    from_city: str
    to_city: str
    from_station: str
    to_station: str
    departure_time: time
    arrival_time: time
    duration_minutes: int
    price: float
    company: str
    flight_train_no: str


class RoutePlan(BaseModel):
    id: str
    total_price: float
    total_duration_minutes: int
    transfer_count: int
    legs: List[Leg]


class SearchRequest(BaseModel):
    from_city: str
    to_city: str
    travel_date: date
    optimization_target: OptimizationTarget = OptimizationTarget.BALANCED
    max_transfers: Optional[int] = 3


class SearchResponse(BaseModel):
    routes: List[RoutePlan]
    total_count: int


# 模拟搜索结果数据
def generate_mock_routes(from_city: str, to_city: str) -> List[RoutePlan]:
    """生成模拟路线数据"""
    return [
        RoutePlan(
            id="route_1",
            total_price=850.0,
            total_duration_minutes=180,
            transfer_count=0,
            legs=[
                Leg(
                    transport_type=TransportType.FLIGHT,
                    from_city=from_city,
                    to_city=to_city,
                    from_station=f"{from_city}机场",
                    to_station=f"{to_city}机场",
                    departure_time=time(8, 30),
                    arrival_time=time(11, 30),
                    duration_minutes=180,
                    price=850.0,
                    company="中国国航",
                    flight_train_no="CA1234"
                )
            ]
        ),
        RoutePlan(
            id="route_2",
            total_price=550.0,
            total_duration_minutes=300,
            transfer_count=0,
            legs=[
                Leg(
                    transport_type=TransportType.TRAIN,
                    from_city=from_city,
                    to_city=to_city,
                    from_station=f"{from_city}南站",
                    to_station=f"{to_city}站",
                    departure_time=time(9, 0),
                    arrival_time=time(14, 0),
                    duration_minutes=300,
                    price=550.0,
                    company="中国铁路",
                    flight_train_no="G123"
                )
            ]
        ),
        RoutePlan(
            id="route_3",
            total_price=680.0,
            total_duration_minutes=420,
            transfer_count=1,
            legs=[
                Leg(
                    transport_type=TransportType.FLIGHT,
                    from_city=from_city,
                    to_city="NJ",
                    from_station=f"{from_city}机场",
                    to_station="南京禄口机场",
                    departure_time=time(7, 0),
                    arrival_time=time(9, 0),
                    duration_minutes=120,
                    price=450.0,
                    company="东方航空",
                    flight_train_no="MU5678"
                ),
                Leg(
                    transport_type=TransportType.TRAIN,
                    from_city="NJ",
                    to_city=to_city,
                    from_station="南京南站",
                    to_station=f"{to_city}站",
                    departure_time=time(11, 0),
                    arrival_time=time(14, 0),
                    duration_minutes=180,
                    price=230.0,
                    company="中国铁路",
                    flight_train_no="G789"
                )
            ]
        ),
    ]


@router.post("/search", response_model=SearchResponse)
def search_routes(request: SearchRequest):
    """搜索路线"""
    routes = generate_mock_routes(request.from_city, request.to_city)
    return SearchResponse(
        routes=routes,
        total_count=len(routes)
    )
