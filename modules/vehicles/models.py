"""SQLAlchemy models for vehicle and driver booking details."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.base import Base


class VehicleDetails(Base):
    """Vehicle measurements and the resulting eligibility decision."""

    __tablename__ = "vehicle_details"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_vehicle_details_booking_id"),
        Index("ix_vehicle_details_booking_id", "booking_id"),
        Index("ix_vehicle_details_registration_number", "registration_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(32), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(100), nullable=False)
    gvw_tonnes: Mapped[float] = mapped_column(Float, nullable=False)
    height_m: Mapped[float] = mapped_column(Float, nullable=False)
    length_m: Mapped[float] = mapped_column(Float, nullable=False)
    width_m: Mapped[float] = mapped_column(Float, nullable=False)
    eligibility_status: Mapped[str] = mapped_column(String(16), nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    rejections: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DriverDetails(Base):
    """Driver identity and accompaniment details for a booking."""

    __tablename__ = "driver_details"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_driver_details_booking_id"),
        Index("ix_driver_details_booking_id", "booking_id"),
        Index("ix_driver_details_mobile_number", "mobile_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    driver_name: Mapped[str] = mapped_column(String(100), nullable=False)
    mobile_number: Mapped[str] = mapped_column(String(10), nullable=False)
    licence_number: Mapped[str] = mapped_column(String(64), nullable=False)
    accompanying: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
