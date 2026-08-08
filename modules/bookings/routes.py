from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from .exceptions import (
    BookingAccessDeniedException,
    BookingNotFoundException,
    InvalidBookingStateTransitionException,
    InvalidEwayBillException,
    ReservationExpiredException,
    VehicleNotEligibleException,
    VehicleNotFoundException,
)
from .enums import BookingStatus
from .repository import BookingsRepository, SQLAlchemyBookingsRepository
from .schemas import (
    BookingStatusResponse,
    CreateBookingRequest,
    CreateBookingResponse,
    ErrorResponse,
    BookingQRResponse,
)
from .services.bookings_service import BookingsService
from .services.qr_service import QRService, MissingQRSecretError
import os

logger = logging.getLogger(__name__)


class BadRequestValidationRoute(APIRoute):
    def get_route_handler(
        self,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_handler = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=[
                        {key: value for key, value in error.items() if key != "ctx"}
                        for error in exc.errors()
                    ],
                ) from exc

        return handler


router = APIRouter(
    prefix="/api/v1/bookings",
    tags=["Bookings"],
    route_class=BadRequestValidationRoute,
)


class _DevUser:
    def __init__(self, id: uuid.UUID | None = None, is_admin: bool = False) -> None:
        self.id = id or uuid.UUID(int=1)
        self.is_admin = is_admin
        self.role = "COMPANY_USER" if not is_admin else "ADMIN"


def get_current_user() -> Any:
    """Development-only mock authentication dependency.

    This returns a predictable fake user so Swagger UI can be used locally
    without the full auth system wired. Replace with the real dependency
    `core.dependencies.get_current_user` in production.
    """
    return _DevUser()


def get_repository(session: AsyncSession = Depends(get_db)) -> BookingsRepository:
    return SQLAlchemyBookingsRepository(session)


def get_booking_service(
    repository: BookingsRepository = Depends(get_repository),
    session: AsyncSession = Depends(get_db),
) -> BookingsService:
    return BookingsService(
        repository=repository,
        session=session,
        reservation_service=object(),
        eway_bill_service=object(),
        vehicles_service=object(),
        pricing_service=object(),
    )


def get_qr_service() -> QRService:
    """Dependency factory for QRService.

    Tries to initialize with `GATE_QR_SECRET` from environment. In
    development, falls back to a deterministic dev secret to keep the
    endpoint usable in local testing.
    """
    secret = os.environ.get("GATE_QR_SECRET")
    try:
        return QRService(gate_qr_secret=secret)
    except MissingQRSecretError:
        # Development fallback
        dev_secret = "dev-qr-secret-32-bytes-minimum!!"
        logging.getLogger(__name__).warning(
            "GATE_QR_SECRET not set; using development fallback secret"
        )
        return QRService(gate_qr_secret=dev_secret)


@router.post(
    "",
    response_model=CreateBookingResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request format"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not found"},
        409: {"model": ErrorResponse, "description": "Conflict"},
    },
)
async def create_booking(
    payload: CreateBookingRequest,
    current_user: Any = Depends(get_current_user),
    service: BookingsService = Depends(get_booking_service),
) -> CreateBookingResponse:
    try:
        return await service.create_booking(payload, current_user.id)
    except ReservationExpiredException | InvalidEwayBillException | VehicleNotFoundException | VehicleNotEligibleException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except BookingAccessDeniedException as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except BookingNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "",
    response_model=list[BookingStatusResponse],
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
async def list_bookings(
    current_user: Any = Depends(get_current_user),
    service: BookingsService = Depends(get_booking_service),
) -> list[BookingStatusResponse]:
    return await service.list_user_bookings(current_user)


@router.get(
    "/{booking_id}",
    response_model=BookingStatusResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_booking(
    booking_id: UUID,
    current_user: Any = Depends(get_current_user),
    service: BookingsService = Depends(get_booking_service),
) -> BookingStatusResponse:
    try:
        return await service.get_booking(booking_id, current_user)
    except BookingNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BookingAccessDeniedException as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/{booking_id}/status",
    response_model=BookingStatusResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_booking_status(
    booking_id: UUID,
    current_user: Any = Depends(get_current_user),
    service: BookingsService = Depends(get_booking_service),
) -> BookingStatusResponse:
    try:
        return await service.get_booking_status(booking_id, current_user)
    except BookingNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BookingAccessDeniedException as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.patch(
    "/{booking_id}/cancel",
    response_model=BookingStatusResponse,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def cancel_booking(
    booking_id: UUID,
    current_user: Any = Depends(get_current_user),
    service: BookingsService = Depends(get_booking_service),
) -> BookingStatusResponse:
    try:
        return await service.transition_state(booking_id, BookingStatus.CANCELLED, current_user)
    except BookingNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BookingAccessDeniedException as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidBookingStateTransitionException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/{booking_id}/qr",
    response_model=BookingQRResponse,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_booking_qr(
    booking_id: UUID,
    current_user: Any = Depends(get_current_user),
    service: BookingsService = Depends(get_booking_service),
    qr_service: QRService = Depends(get_qr_service),
) -> BookingQRResponse:
    try:
        return await service.get_booking_qr(booking_id, current_user, qr_service)
    except BookingNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BookingAccessDeniedException as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        # Generic 500 for unexpected QR errors
        logging.exception("Failed to generate or retrieve booking QR")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
