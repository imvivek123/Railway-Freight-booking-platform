from __future__ import annotations

from decimal import Decimal
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Booking
from .enums import BookingStatus


class BookingsRepositoryError(RuntimeError):
    """Raised when booking persistence fails."""


class BookingsRepository(Protocol):
    """Repository contract used by the booking service."""

    async def create_booking(
        self,
        *,
        booking_number: str,
        user_id: UUID,
        vehicle_id: UUID,
        reservation_id: UUID,
        status: BookingStatus,
        eway_bill_data: dict[str, Any],
        price_snapshot: dict[str, Any],
        driver_name: str,
        driver_mobile: str,
        driver_license: str,
        total_amount: Decimal,
    ) -> Booking: ...

    async def get_by_id(self, booking_id: UUID) -> Booking | None: ...

    async def get_by_user(self, user_id: UUID) -> list[Booking]: ...

    async def update_booking_status(
        self, booking_id: UUID, status: BookingStatus
    ) -> Booking: ...

    async def bulk_update_status_by_rake(
        self, rake_id: UUID, status: BookingStatus
    ) -> int: ...

    async def list_user_bookings(self, user_id: UUID | None = None) -> list[Booking]: ...


class SQLAlchemyBookingsRepository:
    """SQLAlchemy implementation of the booking repository contract."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_booking(
        self,
        *,
        booking_number: str,
        user_id: UUID,
        vehicle_id: UUID,
        reservation_id: UUID,
        status: BookingStatus,
        eway_bill_data: dict[str, Any],
        price_snapshot: dict[str, Any],
        driver_name: str,
        driver_mobile: str,
        driver_license: str,
        total_amount: Decimal,
    ) -> Booking:
        booking = Booking(
            booking_number=booking_number,
            user_id=user_id,
            vehicle_id=vehicle_id,
            reservation_id=reservation_id,
            status=status.value,
            eway_bill_data=eway_bill_data,
            price_snapshot=price_snapshot,
            driver_name=driver_name,
            driver_mobile=driver_mobile,
            driver_license=driver_license,
            total_amount=total_amount,
        )
        self._session.add(booking)
        try:
            await self._session.flush()
            await self._session.refresh(booking)
        except SQLAlchemyError as exc:
            raise BookingsRepositoryError("Failed to persist booking") from exc
        return booking

    async def get_by_id(self, booking_id: UUID) -> Booking | None:
        try:
            result = await self._session.execute(
                select(Booking).where(Booking.id == booking_id)
            )
        except SQLAlchemyError as exc:
            raise BookingsRepositoryError("Failed to load booking") from exc
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: UUID) -> list[Booking]:
        try:
            result = await self._session.execute(
                select(Booking)
                .where(Booking.user_id == user_id)
                .order_by(Booking.created_at.desc())
            )
        except SQLAlchemyError as exc:
            raise BookingsRepositoryError("Failed to load user bookings") from exc
        return result.scalars().all()

    async def update_booking_status(
        self, booking_id: UUID, status: BookingStatus
    ) -> Booking:
        try:
            result = await self._session.execute(
                update(Booking)
                .where(Booking.id == booking_id)
                .values(status=status.value, updated_at=func.now())
                .returning(Booking)
            )
        except SQLAlchemyError as exc:
            raise BookingsRepositoryError("Failed to update booking status") from exc
        booking = result.scalar_one_or_none()
        if booking is None:
            raise BookingsRepositoryError("Booking not found for status update")
        return booking

    async def bulk_update_status_by_rake(
        self, rake_id: UUID, status: BookingStatus
    ) -> int:
        try:
            result = await self._session.execute(
                update(Booking)
                .where(Booking.reservation_id == rake_id)
                .values(status=status.value, updated_at=func.now())
            )
        except SQLAlchemyError as exc:
            raise BookingsRepositoryError(
                "Failed to bulk update booking status by rake"
            ) from exc
        return result.rowcount or 0

    async def list_user_bookings(self, user_id: UUID | None = None) -> list[Booking]:
        try:
            statement = select(Booking).order_by(Booking.created_at.desc())
            if user_id is not None:
                statement = statement.where(Booking.user_id == user_id)
            result = await self._session.execute(statement)
        except SQLAlchemyError as exc:
            raise BookingsRepositoryError("Failed to list bookings") from exc
        return result.scalars().all()
