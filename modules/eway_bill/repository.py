"""Persistence boundary for E-Way Bill lookup results."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EWayBill


class EWayBillPersistenceError(RuntimeError):
    """Raised when an E-Way Bill result cannot be persisted."""


class EWayBillRepository(Protocol):
    """Repository contract consumed by the service layer."""

    async def create(
        self,
        *,
        booking_id: UUID,
        eway_bill_number: str,
        status: str,
        validity: datetime,
        raw_response: dict[str, Any],
    ) -> EWayBill:
        """Persist and return one lookup result."""
        ...


class SQLAlchemyEWayBillRepository:
    """SQLAlchemy implementation of the E-Way Bill repository contract."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        booking_id: UUID,
        eway_bill_number: str,
        status: str,
        validity: datetime,
        raw_response: dict[str, Any],
    ) -> EWayBill:
        """Insert a lookup atomically, rolling back a failed transaction."""
        record = EWayBill(
            booking_id=booking_id,
            eway_bill_number=eway_bill_number,
            status=status,
            validity=validity,
            raw_response=raw_response,
        )
        self._session.add(record)
        try:
            await self._session.commit()
            await self._session.refresh(record)
        except SQLAlchemyError as exc:
            await self._session.rollback()
            raise EWayBillPersistenceError(
                "Failed to persist E-Way Bill lookup"
            ) from exc
        return record

