"""Database models owned by the E-Way Bill module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base import Base


class EWayBill(Base):
    """Persisted result of a GST E-Way Bill lookup."""

    __tablename__ = "eway_bills"
    __table_args__ = (
        Index("ix_eway_bills_booking_id", "booking_id"),
        Index("ix_eway_bills_eway_bill_number", "eway_bill_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    eway_bill_number: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    validity: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
