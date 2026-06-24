"""FastAPI routes and dependency wiring for vehicle-driver onboarding."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db

from .exceptions import (
    InvalidDriverDataException,
    InvalidVehicleDataException,
    VehicleDriverPersistenceException,
    VehicleRejectedException,
)
from .repository import SQLAlchemyVehicleDriverRepository, VehicleDriverRepository
from .schemas import ErrorResponse, VehicleDriverSaveRequest, VehicleDriverSaveResponse
from .services.vehicles_service import VehicleDriverService

logger = logging.getLogger(__name__)


class BadRequestValidationRoute(APIRoute):
    """Return HTTP 400 instead of FastAPI's default 422 for invalid input."""

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
    prefix="/api/v1/vehicle-driver",
    tags=["Vehicle and Driver"],
    route_class=BadRequestValidationRoute,
)


def get_repository(
    session: AsyncSession = Depends(get_db),
) -> VehicleDriverRepository:
    """Create the request-scoped SQLAlchemy repository."""
    return SQLAlchemyVehicleDriverRepository(session)


def get_service(
    repository: VehicleDriverRepository = Depends(get_repository),
) -> VehicleDriverService:
    """Compose a service from its replaceable repository dependency."""
    return VehicleDriverService(repository)


@router.post(
    "/save",
    response_model=VehicleDriverSaveResponse,
    responses={
        200: {
            "description": "Vehicle and driver details saved",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ELIGIBLE",
                        "vehicle_status": "ELIGIBLE",
                        "driver_status": "VALID",
                        "warnings": [],
                        "rejections": [],
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid vehicle or driver data",
            "content": {
                "application/json": {
                    "examples": {
                        "vehicle": {
                            "value": {"detail": "Invalid vehicle dimensions"}
                        },
                        "mobile": {"value": {"detail": "Invalid mobile number"}},
                    }
                }
            },
        },
        503: {"model": ErrorResponse, "description": "Database unavailable"},
    },
)
async def save_vehicle_driver(
    payload: VehicleDriverSaveRequest,
    service: VehicleDriverService = Depends(get_service),
) -> VehicleDriverSaveResponse:
    """Validate and save vehicle and driver details for a booking."""
    try:
        return await service.save(payload)
    except (InvalidVehicleDataException, InvalidDriverDataException) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except VehicleRejectedException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except VehicleDriverPersistenceException as exc:
        logger.exception("Vehicle-driver persistence failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable",
        ) from exc
