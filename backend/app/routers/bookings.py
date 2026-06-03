from fastapi import APIRouter, Depends

from app.schemas import BookingCreateRequest, BookingCreateResponse
from app.services.user_service import AuthenticatedUser, UserService, get_current_user, get_user_service, require_csrf

router = APIRouter(prefix="/bookings")


@router.post("", response_model=BookingCreateResponse, dependencies=[Depends(require_csrf)])
def create_booking(
    payload: BookingCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> BookingCreateResponse:
    return user_service.create_booking(
        current_user.user.id,
        payload.route_id,
        [leg.model_dump(mode="json") for leg in payload.legs],
    )
