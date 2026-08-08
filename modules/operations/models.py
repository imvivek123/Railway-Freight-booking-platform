"""ORM models for the operations tables (migration 0001).

gate_entries, loading_plans and loading_plan_items back the terminal gate and
loading flows. Following the convention set by the Booking model, no ORM-level
ForeignKeys or relationships are declared — the real FK constraints live in
migration 0001, and omitting them here keeps mapper configuration and the
test-suite's metadata.create_all free of cross-module registration ordering.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Uuid,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class GateEntry(Base):
    __tablename__ = "gate_entries"

    entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    terminal_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    entry_type: Mapped[str | None] = mapped_column(String(5), nullable=True)
    entry_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    qr_scanned: Mapped[bool] = mapped_column(Boolean, server_default=false())
    scanned_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    manual_override: Mapped[bool] = mapped_column(Boolean, server_default=false())
    override_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    override_approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    actual_gvw_t: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    actual_height_m: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    weight_variance_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    parking_bay: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GateOverrideAudit(Base):
    __tablename__ = "gate_override_audit"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    supervisor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    old_status: Mapped[str] = mapped_column(String(30), nullable=False)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LoadingPlan(Base):
    __tablename__ = "loading_plans"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rake_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    plan_status: Mapped[str] = mapped_column(String(20), server_default="DRAFT")
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    generated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    loading_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    loading_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class LoadingPlanItem(Base):
    __tablename__ = "loading_plan_items"

    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    wagon_number: Mapped[int] = mapped_column(Integer, nullable=False)
    load_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    declared_gvw_t: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    loaded: Mapped[bool] = mapped_column(Boolean, server_default=false())
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    loaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
