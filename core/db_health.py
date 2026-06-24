"""Database connectivity health endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from .database import check_database_connection

logger = logging.getLogger("railro.database.health")
router = APIRouter(tags=["System"])


@router.get("/db-health")
async def database_health() -> dict[str, str]:
    """Return connected when PostgreSQL successfully executes SELECT 1."""
    try:
        await check_database_connection()
    except Exception as exc:
        logger.exception("Database health endpoint reported unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable",
        ) from exc
    return {"status": "connected"}

