from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, String, UniqueConstraint, func, Numeric, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base import Base


class Booking(Base):
    """Booking entity persisted for every confirmed slot reservation."""

    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("booking_number", name="uq_bookings_booking_number"),
        Index("ix_bookings_user_id", "user_id"),
        Index("ix_bookings_reservation_id", "reservation_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_number: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reservation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    eway_bill_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    price_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    driver_name: Mapped[str] = mapped_column(String(100), nullable=False)
    driver_mobile: Mapped[str] = mapped_column(String(15), nullable=False)
    driver_license: Mapped[str] = mapped_column(String(64), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
