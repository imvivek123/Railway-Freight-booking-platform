import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.events import Events, publish
from core.exceptions import ConflictException, NotFoundException, PermissionException
from core.security import verify_qr_payload
from modules.bookings.models import Booking
from modules.bookings.services.booking_state_service import (
    transition_to_completed,
    transition_to_gate_entry,
    transition_to_loaded,
    transition_to_no_show,
    transition_to_unloaded,
)
from modules.inventory.models import Rake, Terminal
from modules.operations.schemas import (
    GateOverrideRequest,
    GateScanRequest,
    GateScanResponse,
    MarkLoadedRequest,
)
from modules.operations.services.loading_plan_service import (
    bulk_transition_to_arrived as bulk_transition_to_arrived_service,
)
from modules.operations.services.loading_plan_service import (
    bulk_transition_to_in_transit as bulk_transition_to_in_transit_service,
)
from modules.operations.services.loading_plan_service import (
    mark_booking_loaded as mark_booking_loaded_service,
)

logger = logging.getLogger(__name__)
_OVERRIDE_ROLES = {"COMPANY_OPERATIONS_SUPERVISOR", "ADMIN"}

# Phase 1 — Gate operations cover QR scan + state transitions only.
# Weighbridge (GVW) measurements are performed physically at the terminal
# and are NOT recorded digitally in Phase 1.


async def scan_gate_qr(
    payload: GateScanRequest,
    operator,
    db: AsyncSession,
) -> GateScanResponse:
    from modules.bookings.repository import get_booking_by_id

    # Validate QR signature
    try:
        qr_data = verify_qr_payload(payload.qr_payload)
    except ValueError as e:
        raise PermissionException("QR signature is invalid — booking cannot be verified") from e

    booking_id = UUID(qr_data["booking_id"])
    booking = await get_booking_by_id(booking_id, db)
    if not booking:
        raise NotFoundException("Booking", str(booking_id))

    # Ops staff act at their assigned terminal; ADMIN may pass one explicitly.
    terminal_id = getattr(operator, "assigned_terminal_id", None) or payload.terminal_id
    if terminal_id is None:
        raise PermissionException("No terminal is associated with this operator")

    return await _process_gate_transition(booking, terminal_id, payload.entry_type, operator, db)


async def manual_gate_entry(payload, operator, db: AsyncSession) -> GateScanResponse:
    """Gate desk fallback: look a booking up by its number (typed by the operator)
    instead of scanning the signed QR, then apply the same IN/OUT transition."""
    from modules.bookings.repository import get_booking_by_number

    booking = await get_booking_by_number(payload.booking_number, db)
    if not booking:
        raise NotFoundException("Booking", payload.booking_number)

    # Ops staff act at their assigned terminal; ADMIN may pass one explicitly.
    terminal_id = getattr(operator, "assigned_terminal_id", None) or payload.terminal_id
    if terminal_id is None:
        raise PermissionException("No terminal is associated with this operator")

    return await _process_gate_transition(booking, terminal_id, payload.entry_type, operator, db)


async def _process_gate_transition(
    booking,
    terminal_id: UUID,
    entry_type: str,
    operator,
    db: AsyncSession,
) -> GateScanResponse:
    """Shared core for QR and manual gate scans.

    IN  → CONFIRMED → GATE_ENTRY → LOADED   (truck driven onto the rake)
    OUT → ARRIVED   → UNLOADED   → COMPLETED (truck driven off at destination;
                                              invoicing fires on the UNLOADED event)
    """
    from modules.operations.repository import create_gate_entry

    _validate_terminal(booking, terminal_id, entry_type)
    _validate_duplicate_scan(booking.booking_status, entry_type)

    if entry_type == "IN":
        await _validate_gate_window(booking, db)
        await transition_to_gate_entry(booking.booking_id, db)
        await transition_to_loaded(booking.booking_id, db)
        new_status = "LOADED"
        message = f"Gate-in scan recorded — booking {booking.booking_number} marked LOADED"
    elif entry_type == "OUT":
        await transition_to_unloaded(booking.booking_id, db)
        await transition_to_completed(booking.booking_id, db)
        new_status = "COMPLETED"
        message = "Gate-out scan recorded — booking marked UNLOADED then COMPLETED. Invoice triggered."
    else:
        raise PermissionException(f"Unknown entry_type: {entry_type}")

    await create_gate_entry(
        booking_id=booking.booking_id,
        terminal_id=terminal_id,
        entry_type=entry_type,
        scanned_by=operator.user_id,
        manual_override=False,
        db=db,
    )

    logger.info(
        "Gate scan processed",
        extra={
            "booking_id": str(booking.booking_id),
            "entry_type": entry_type,
            "operator": str(operator.user_id),
            "new_status": new_status,
        },
    )

    return GateScanResponse(
        booking_id=booking.booking_id,
        booking_number=booking.booking_number,
        vehicle_registration=booking.vehicle_registration,
        new_status=new_status,
        parking_bay=None,  # assigned on gate_entries, not the booking
        message=message,
    )


async def override_gate_entry(
    payload: GateOverrideRequest,
    supervisor,
    db: AsyncSession,
) -> GateScanResponse:
    from modules.bookings.repository import get_booking_by_id
    from modules.operations.repository import create_gate_entry, create_override_audit

    _validate_supervisor_role(supervisor)

    booking = await get_booking_by_id(payload.booking_id, db)
    if not booking:
        raise NotFoundException("Booking", str(payload.booking_id))

    old_status = booking.booking_status
    if payload.entry_type == "IN":
        await transition_to_gate_entry(payload.booking_id, db)
        new_status = "GATE_ENTRY"
    else:
        await transition_to_unloaded(payload.booking_id, db)
        new_status = "UNLOADED"

    await create_gate_entry(
        booking_id=payload.booking_id,
        terminal_id=payload.terminal_id,
        entry_type=payload.entry_type,
        scanned_by=supervisor.user_id,
        manual_override=True,
        override_reason=payload.override_reason,
        override_approved_by=supervisor.user_id,
        db=db,
    )
    await create_override_audit(
        booking_id=payload.booking_id,
        supervisor_id=supervisor.user_id,
        old_status=old_status,
        new_status=new_status,
        override_reason=payload.override_reason,
        db=db,
    )

    logger.warning(
        "Gate override used",
        extra={
            "booking_id": str(payload.booking_id),
            "supervisor": str(supervisor.user_id),
            "reason": payload.override_reason,
        },
    )

    return GateScanResponse(
        booking_id=booking.booking_id,
        booking_number=booking.booking_number,
        vehicle_registration=booking.vehicle_registration,
        new_status=new_status,
        parking_bay=None,  # assigned on gate_entries, not the booking
        message=f"Override applied by supervisor. Reason: {payload.override_reason}",
    )


async def mark_booking_loaded(
    rake_id: str,
    payload: MarkLoadedRequest,
    operator,
    db: AsyncSession,
) -> dict:
    return await mark_booking_loaded_service(UUID(rake_id), payload, operator, db)


async def mark_rake_departed(rake_id: str, db: AsyncSession) -> dict:
    """Advance every LOADED booking on a rake to IN_TRANSIT and mark the rake departed.

    Bridges the gap between loading (LOADED) and the destination gate-out scan, which
    requires bookings to reach ARRIVED before UNLOADED. Any booking still CONFIRMED at
    departure (never gate-scanned-in) is a no-show at entry and is swept to NO_SHOW.
    """
    rid = UUID(rake_id)
    rake = await db.scalar(select(Rake).where(Rake.id == rid))
    if rake is None:
        raise NotFoundException("Rake", rake_id)

    count = await bulk_transition_to_in_transit_service(rid, db)
    no_shows = await _sweep_entry_no_shows(rid, db)
    rake.status = "IN_TRANSIT"
    await publish(
        Events.RAKE_DEPARTED,
        {"rake_id": rake_id, "bookings_transitioned": count, "no_shows": no_shows},
    )
    return {
        "rake_id": rake_id,
        "status": "IN_TRANSIT",
        "bookings_transitioned": count,
        "no_shows": no_shows,
        "message": f"Rake departed; {count} in transit, {no_shows} no-show at entry",
    }


async def _sweep_entry_no_shows(rake_id: UUID, db: AsyncSession) -> int:
    """Mark every still-CONFIRMED booking on a departing rake as NO_SHOW (no gate entry)."""
    result = await db.execute(
        select(Booking).where(Booking.rake_id == rake_id, Booking.booking_status == "CONFIRMED")
    )
    count = 0
    for booking in result.scalars().all():
        await transition_to_no_show(booking.booking_id, db)
        count += 1
    return count


async def mark_booking_no_show_at_exit(booking_id: str, db: AsyncSession) -> dict:
    """Manually mark an ARRIVED booking as NO_SHOW (train arrived, never gate-scanned-out)."""
    bid = UUID(booking_id)
    await transition_to_no_show(bid, db)
    return {
        "booking_id": booking_id,
        "status": "NO_SHOW",
        "message": "Booking marked as no-show at exit",
    }


async def mark_rake_arrived(rake_id: str, db: AsyncSession) -> dict:
    """Advance every IN_TRANSIT booking on a rake to ARRIVED and mark the rake arrived.

    After this, each booking is eligible for the destination gate-out scan
    (ARRIVED → UNLOADED), which triggers invoice generation.
    """
    rid = UUID(rake_id)
    rake = await db.scalar(select(Rake).where(Rake.id == rid))
    if rake is None:
        raise NotFoundException("Rake", rake_id)

    count = await bulk_transition_to_arrived_service(rid, db)
    rake.status = "ARRIVED"
    await publish(Events.RAKE_ARRIVED, {"rake_id": rake_id, "bookings_transitioned": count})
    return {
        "rake_id": rake_id,
        "status": "ARRIVED",
        "bookings_transitioned": count,
        "message": f"Rake arrived; {count} booking(s) ready for gate-out",
    }


def _validate_terminal(booking, terminal_id: UUID, entry_type: str) -> None:
    # IN happens at the origin terminal, OUT at the destination terminal.
    if entry_type == "IN" and booking.origin_terminal_id != terminal_id:
        raise PermissionException("Booking is not valid for this origin terminal")
    if entry_type == "OUT" and booking.destination_terminal_id != terminal_id:
        raise PermissionException("Booking is not valid for this destination terminal")


async def _validate_gate_window(booking, db: AsyncSession) -> None:
    gate_open_time = getattr(booking, "gate_open_time", None)
    if gate_open_time is None:
        departure_time = getattr(booking, "departure_time", None)
        if departure_time is None:
            departure_time = await _get_rake_departure_time(booking.rake_id, db)
        gate_open_time = departure_time - timedelta(hours=3)

    if _now_for(gate_open_time) < gate_open_time:
        raise PermissionException("Gate is not open for this booking yet")


async def _get_rake_departure_time(rake_id: UUID, db: AsyncSession) -> datetime:
    result = await db.execute(select(Rake.scheduled_departure).where(Rake.id == rake_id))
    departure_time = result.scalar_one_or_none()
    if departure_time is None:
        raise NotFoundException("Rake", str(rake_id))
    return departure_time


def _now_for(value: datetime) -> datetime:
    if value.tzinfo is None:
        return datetime.now()
    return datetime.now(UTC)


def _validate_duplicate_scan(current_status: str, entry_type: str) -> None:
    # IN now ends at LOADED; OUT ends at COMPLETED. Guard against re-scanning a
    # booking that has already passed the corresponding gate.
    if entry_type == "IN" and current_status in ("GATE_ENTRY", "LOADED"):
        raise ConflictException("DUPLICATE_GATE_ENTRY", "Booking has already entered the gate")
    if entry_type == "OUT" and current_status in ("UNLOADED", "COMPLETED"):
        raise ConflictException("DUPLICATE_GATE_EXIT", "Booking has already exited the gate")


def _validate_supervisor_role(supervisor) -> None:
    role = getattr(supervisor, "user_role", None)
    if role not in _OVERRIDE_ROLES:
        raise PermissionException(f"Role '{role}' not permitted for gate override")


# ─── Ops read surface (terminal-scoped lists + dashboard) ────────────────────
#
# Ops staff/supervisors are internal users bound to a single terminal
# (assigned_terminal_id). Every read below is scoped to that terminal; ADMIN
# (no terminal) sees everything.

# Bookings that are "live at a terminal" for the loading/arrival queues.
_LOADING_STATUSES = ("GATE_ENTRY", "LOADED")
_ARRIVAL_STATUSES = ("ARRIVED", "UNLOADED", "COMPLETED")


def _operator_terminal(operator) -> UUID | None:
    """The terminal an ops user is scoped to, or None for ADMIN (see all)."""
    role = getattr(operator, "user_role", None)
    if role in ("ADMIN", "PLATFORM_ADMIN"):
        return None
    return getattr(operator, "assigned_terminal_id", None)


async def list_ops_bookings(
    operator, db: AsyncSession, *, status: str | None = None, rake_id: UUID | None = None
) -> list[dict]:
    """Bookings (with vehicle/driver/route/rake/status) for the ops queues.

    Scoped to the operator's terminal — a booking is included if the terminal is
    either its origin (loading) or destination (arrival). Optional filters by a
    single status or a comma-separated status list, and by rake.
    """
    origin = Terminal.__table__.alias("origin")
    dest = Terminal.__table__.alias("dest")
    b = Booking.__table__

    stmt = (
        select(
            b.c.booking_id,
            b.c.booking_number,
            b.c.vehicle_registration,
            b.c.vehicle_type,
            b.c.driver_name,
            b.c.booking_status,
            b.c.created_at,
            b.c.rake_id,
            Rake.rake_number,
            origin.c.station_code.label("origin_code"),
            dest.c.station_code.label("dest_code"),
        )
        .select_from(b)
        .join(Rake.__table__, Rake.__table__.c.rake_id == b.c.rake_id)
        .join(origin, origin.c.terminal_id == b.c.origin_terminal_id)
        .join(dest, dest.c.terminal_id == b.c.destination_terminal_id)
        .order_by(b.c.created_at.desc())
    )

    terminal_id = _operator_terminal(operator)
    if terminal_id is not None:
        stmt = stmt.where(
            or_(b.c.origin_terminal_id == terminal_id, b.c.destination_terminal_id == terminal_id)
        )
    if status:
        statuses = [s.strip().upper() for s in status.split(",") if s.strip()]
        if statuses:
            stmt = stmt.where(b.c.booking_status.in_(statuses))
    if rake_id is not None:
        stmt = stmt.where(b.c.rake_id == rake_id)

    rows = await db.execute(stmt)
    return [
        {
            "booking_id": str(r.booking_id),
            "booking_number": r.booking_number,
            "vehicle_registration": r.vehicle_registration,
            "vehicle_type": r.vehicle_type,
            "driver_name": r.driver_name,
            "status": r.booking_status,
            "route": f"{r.origin_code} → {r.dest_code}",
            "rake_id": str(r.rake_id),
            "rake_number": r.rake_number,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


async def get_ops_dashboard(operator, db: AsyncSession) -> dict:
    """Counts for the ops dashboard, scoped to the operator's terminal."""
    terminal_id = _operator_terminal(operator)
    b = Booking.__table__
    day_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    def _scoped(base):
        if terminal_id is not None:
            return base.where(
                or_(b.c.origin_terminal_id == terminal_id, b.c.destination_terminal_id == terminal_id)
            )
        return base

    loading_queue = await db.scalar(
        _scoped(select(func.count()).select_from(b).where(b.c.booking_status == "GATE_ENTRY"))
    ) or 0
    loaded = await db.scalar(
        _scoped(select(func.count()).select_from(b).where(b.c.booking_status == "LOADED"))
    ) or 0
    in_transit = await db.scalar(
        _scoped(select(func.count()).select_from(b).where(b.c.booking_status == "IN_TRANSIT"))
    ) or 0
    arrived = await db.scalar(
        _scoped(select(func.count()).select_from(b).where(b.c.booking_status == "ARRIVED"))
    ) or 0
    completed_today = await db.scalar(
        _scoped(
            select(func.count())
            .select_from(b)
            .where(b.c.booking_status == "COMPLETED", b.c.created_at >= day_start)
        )
    ) or 0

    return {
        "loading_queue": int(loading_queue),
        "loaded": int(loaded),
        "in_transit": int(in_transit),
        "arrived": int(arrived),
        "completed_today": int(completed_today),
    }


async def list_recent_gate_entries(operator, db: AsyncSession, limit: int = 12) -> list[dict]:
    """Recent gate scans at the operator's terminal for the dashboard feed."""
    from modules.operations.models import GateEntry

    ge = GateEntry.__table__
    b = Booking.__table__
    stmt = (
        select(
            ge.c.entry_id,
            ge.c.entry_type,
            ge.c.entry_time,
            ge.c.manual_override,
            b.c.booking_number,
            b.c.vehicle_registration,
        )
        .select_from(ge)
        .join(b, b.c.booking_id == ge.c.booking_id)
        .order_by(ge.c.entry_time.desc())
        .limit(limit)
    )
    terminal_id = _operator_terminal(operator)
    if terminal_id is not None:
        stmt = stmt.where(ge.c.terminal_id == terminal_id)

    rows = await db.execute(stmt)
    return [
        {
            "entry_id": str(r.entry_id),
            "entry_type": r.entry_type,
            "entry_time": r.entry_time.isoformat() if r.entry_time else None,
            "manual_override": r.manual_override,
            "booking_number": r.booking_number,
            "vehicle_registration": r.vehicle_registration,
        }
        for r in rows
    ]
