"""FastAPI HTTP boundary and dependency wiring for E-Way Bill verification."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db

from .adapters.gst_adapter import GSTAdapter, MockGSTAdapter
from .repository import (
    EWayBillPersistenceError,
    EWayBillRepository,
    SQLAlchemyEWayBillRepository,
)
from .schemas import EWayBillFetchRequest, EWayBillFetchResponse, ErrorResponse
from .services.eway_bill_service import (
    AsyncCache,
    EWayBillService,
    GSTServiceUnavailableError,
    InvalidGSTResponseError,
)

logger = logging.getLogger(__name__)


class BadRequestValidationRoute(APIRoute):
    """Convert validation failures on this API from FastAPI's 422 to HTTP 400."""

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
    prefix="/api/v1/eway",
    tags=["E-Way Bill"],
    route_class=BadRequestValidationRoute,
)


def get_cache(request: Request) -> AsyncCache:
    """Return the async Redis client configured at ``app.state.redis``."""
    cache = getattr(request.app.state, "redis", None)
    if cache is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service is not configured or unavailable",
        )
    return cast(Redis, cache)


def get_gst_adapter() -> GSTAdapter:
    """Provide the mock adapter until a production GST integration is installed."""
    return MockGSTAdapter()


def get_repository(
    session: AsyncSession = Depends(get_db),
) -> EWayBillRepository:
    """Build the SQLAlchemy repository for one request."""
    return SQLAlchemyEWayBillRepository(session)


def get_eway_bill_service(
    repository: EWayBillRepository = Depends(get_repository),
    cache: AsyncCache = Depends(get_cache),
    gst_adapter: GSTAdapter = Depends(get_gst_adapter),
) -> EWayBillService:
    """Compose the service from replaceable dependency boundaries."""
    return EWayBillService(
        repository=repository,
        cache=cache,
        gst_adapter=gst_adapter,
    )


@router.post(
    "/fetch",
    response_model=EWayBillFetchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request format"},
        502: {"model": ErrorResponse, "description": "Invalid/unavailable GST service"},
        503: {"model": ErrorResponse, "description": "Infrastructure unavailable"},
    },
)
async def fetch_eway_bill(
    payload: EWayBillFetchRequest,
    service: EWayBillService = Depends(get_eway_bill_service),
) -> EWayBillFetchResponse:
    """Fetch, validate, persist, and cache an E-Way Bill decision."""
    try:
        return await service.fetch(payload)
    except (GSTServiceUnavailableError, InvalidGSTResponseError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except EWayBillPersistenceError as exc:
        logger.exception("E-Way Bill persistence failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable",
        ) from exc
