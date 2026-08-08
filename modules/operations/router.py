from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import require_role
from modules.operations.schemas import (
    GateOverrideRequest,
    GateScanRequest,
    GateScanResponse,
    ManualGateRequest,
    MarkLoadedRequest,
)
from modules.operations.services.operations_service import (
    get_ops_dashboard,
    list_ops_bookings,
    list_recent_gate_entries,
    manual_gate_entry,
    mark_booking_loaded,
    mark_booking_no_show_at_exit,
    mark_rake_arrived,
    mark_rake_departed,
    override_gate_entry,
    scan_gate_qr,
)

router = APIRouter()

_OPS_ROLES = ("OPS_STAFF", "OPS_SUPERVISOR", "ADMIN", "PLATFORM_ADMIN")

# ─── Gate Entry (QR scan + state update) ─────────────────────────────────────
# Phase 1 scope: QR scan validates booking, checks gate window, transitions state.
# No manual weighbridge or GVW entry — measurements are handled at the physical terminal.


@router.post("/gate/scan", response_model=GateScanResponse)
async def gate_scan(
    payload: GateScanRequest,
    user=Depends(require_role("OPS_STAFF", "OPS_SUPERVISOR")),
    db: AsyncSession = Depends(get_db),
):
    return await scan_gate_qr(payload, user, db)


@router.post("/gate/manual", response_model=GateScanResponse)
async def gate_manual(
    payload: ManualGateRequest,
    user=Depends(require_role("OPS_STAFF", "OPS_SUPERVISOR", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Manual gate entry by booking number (typed) — same transition as a QR scan."""
    return await manual_gate_entry(payload, user, db)


@router.post("/gate/override", response_model=GateScanResponse)
async def gate_override(
    payload: GateOverrideRequest,
    user=Depends(require_role("OPS_SUPERVISOR", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await override_gate_entry(payload, user, db)


# ─── Loading (Phase 1: plain LOADED transition — no wagon plan) ───────────────


@router.post("/loading/{rake_id}/mark-loaded")
async def mark_loaded(
    rake_id: str,
    payload: MarkLoadedRequest,
    user=Depends(require_role("OPS_STAFF", "OPS_SUPERVISOR")),
    db: AsyncSession = Depends(get_db),
):
    return await mark_booking_loaded(rake_id, payload, user, db)


# ─── Rake movement (LOADED → IN_TRANSIT → ARRIVED) ────────────────────────────
# Bridges loading and the destination gate-out scan: bookings must reach ARRIVED
# before the OUT scan can transition them to UNLOADED (which triggers invoicing).


@router.post("/rake/{rake_id}/depart")
async def depart_rake(
    rake_id: str,
    user=Depends(require_role("OPS_SUPERVISOR", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await mark_rake_departed(rake_id, db)


@router.post("/rake/{rake_id}/arrive")
async def arrive_rake(
    rake_id: str,
    user=Depends(require_role("OPS_SUPERVISOR", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    return await mark_rake_arrived(rake_id, db)


@router.post("/booking/{booking_id}/no-show")
async def mark_no_show_at_exit(
    booking_id: str,
    user=Depends(require_role("OPS_SUPERVISOR", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """No-show at exit: an ARRIVED booking whose truck was never gate-scanned out."""
    return await mark_booking_no_show_at_exit(booking_id, db)


# ─── Ops read surface (terminal-scoped) ───────────────────────────────────────


@router.get("/dashboard")
async def ops_dashboard(
    user=Depends(require_role(*_OPS_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await get_ops_dashboard(user, db)


@router.get("/bookings")
async def ops_bookings(
    status: str | None = Query(None, description="Filter by status (comma-separated allowed)"),
    rake_id: UUID | None = Query(None),
    user=Depends(require_role(*_OPS_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await list_ops_bookings(user, db, status=status, rake_id=rake_id)


@router.get("/gate-entries")
async def ops_gate_entries(
    limit: int = Query(12, ge=1, le=100),
    user=Depends(require_role(*_OPS_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await list_recent_gate_entries(user, db, limit=limit)
