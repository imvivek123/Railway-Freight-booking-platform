"""Persistence for the operations flows (gate entries).

These functions are the write side that `operations_service` delegates to. They
rely on the request-scoped session committing via ``get_db`` on success, so they
``flush`` (to populate generated IDs) rather than ``commit``.

Phase 1 has no loading plan (wagon allocation is BE4 scope); the dormant
loading_plans / loading_plan_items tables + models remain for BE4 to revive.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.operations.models import GateEntry, GateOverrideAudit

logger = logging.getLogger(__name__)


async def create_gate_entry(
    *,
    booking_id: UUID,
    terminal_id: UUID,
    entry_type: str,
    scanned_by: UUID,
    db: AsyncSession,
    manual_override: bool = False,
    override_reason: str | None = None,
    override_approved_by: UUID | None = None,
) -> GateEntry:
    """Record a gate IN/OUT event for a booking."""
    entry = GateEntry(
        booking_id=booking_id,
        terminal_id=terminal_id,
        entry_type=entry_type,
        scanned_by=scanned_by,
        qr_scanned=not manual_override,
        manual_override=manual_override,
        override_reason=override_reason,
        override_approved_by=override_approved_by,
    )
    db.add(entry)
    await db.flush()
    return entry


async def create_override_audit(
    *,
    booking_id: UUID,
    supervisor_id: UUID,
    old_status: str,
    new_status: str,
    override_reason: str,
    db: AsyncSession,
) -> GateOverrideAudit:
    """Persist a standalone audit record for a manual gate override."""
    audit = GateOverrideAudit(
        booking_id=booking_id,
        supervisor_id=supervisor_id,
        old_status=old_status,
        new_status=new_status,
        reason=override_reason,
    )
    db.add(audit)
    await db.flush()
    return audit
