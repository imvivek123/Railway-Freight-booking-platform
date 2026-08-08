from uuid import UUID

from pydantic import BaseModel


class GateScanRequest(BaseModel):
    qr_payload: str  # Raw QR content (signed JSON string)
    entry_type: str = "IN"  # IN | OUT
    # Optional: ops staff act at their assigned terminal (derived server-side);
    # ADMIN may pass one explicitly.
    terminal_id: UUID | None = None


class ManualGateRequest(BaseModel):
    """Gate desk fallback — operator types the booking number instead of scanning."""

    booking_number: str
    entry_type: str = "IN"  # IN | OUT
    # Optional: ADMIN may pass a terminal; ops staff use their assigned terminal.
    terminal_id: UUID | None = None


class GateScanResponse(BaseModel):
    booking_id: UUID
    booking_number: str
    vehicle_registration: str
    new_status: str
    parking_bay: str | None = None
    message: str


class GateOverrideRequest(BaseModel):
    booking_id: UUID
    terminal_id: UUID
    entry_type: str = "IN"
    override_reason: str  # QR_DAMAGED | MOBILE_DEAD | SYSTEM_ERROR


class MarkLoadedRequest(BaseModel):
    # Phase 1 marks LOADED as a pure state transition — no wagon plan (BE4 scope).
    booking_id: UUID
