"""Operations service layer for loaded/rake transitions.

Phase 1 has NO loading plan (wagon allocation is BE4 scope): loading is a plain
GATE_ENTRY → LOADED state transition, and rake movement advances the whole rake.
The dormant loading_plans / loading_plan_items tables + models remain for BE4.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.events import Events, publish
from modules.bookings.models import Booking
from modules.bookings.services.booking_state_service import (
    transition_to_arrived,
    transition_to_in_transit,
    transition_to_loaded,
)
from modules.operations.schemas import MarkLoadedRequest


async def mark_booking_loaded(
    rake_id: UUID,
    payload: MarkLoadedRequest,
    operator,
    db: AsyncSession,
) -> dict:
    """Phase 1: mark a gate-entered booking LOADED (pure state transition).

    No loading plan / wagon number — that's BE4. When every gate-entered booking on
    the rake is loaded, RAKE_ALL_LOADED fires so the rake can be departed.
    """
    await transition_to_loaded(payload.booking_id, db)

    if await _all_entered_bookings_loaded(rake_id, db):
        from modules.inventory.models import Rake
        rake = await db.scalar(select(Rake).where(Rake.id == rake_id))
        if rake and rake.status != "IN_TRANSIT" and rake.status != "ARRIVED":
            rake.status = "BOARDING"
            
        await publish(Events.RAKE_ALL_LOADED, {"rake_id": str(rake_id)})

    return {
        "message": "Booking marked as loaded",
        "booking_id": str(payload.booking_id),
    }


async def _all_entered_bookings_loaded(rake_id: UUID, db: AsyncSession) -> bool:
    """True when at least one booking on the rake is LOADED and none are still GATE_ENTRY.

    A booking still in GATE_ENTRY has entered the gate but isn't loaded yet, so loading
    is incomplete. CONFIRMED bookings (never entered) don't block — they become no-shows
    at departure.
    """
    pending = await db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.rake_id == rake_id, Booking.booking_status == "GATE_ENTRY")
    )
    loaded = await db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.rake_id == rake_id, Booking.booking_status == "LOADED")
    )
    return (pending or 0) == 0 and (loaded or 0) > 0


async def bulk_transition_to_in_transit(rake_id: UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(Booking).where(Booking.rake_id == rake_id, Booking.booking_status == "LOADED")
    )
    bookings = list(result.scalars().all())
    count = 0
    for booking in bookings:
        await transition_to_in_transit(booking.booking_id, db)
        count += 1
    return count


async def bulk_transition_to_arrived(rake_id: UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(Booking).where(Booking.rake_id == rake_id, Booking.booking_status == "IN_TRANSIT")
    )
    bookings = list(result.scalars().all())
    count = 0
    for booking in bookings:
        await transition_to_arrived(booking.booking_id, db)
        count += 1
    return count
