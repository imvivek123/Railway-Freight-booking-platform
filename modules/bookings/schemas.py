from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import BookingStatus


class CreateBookingRequest(BaseModel):
    """Payload required to create a new booking."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    eway_bill_number: str = Field(
        min_length=1,
        max_length=64,
        description="E-Way Bill number associated with the booking.",
    )
    vehicle_id: UUID = Field(description="Identifier of the vehicle to book.")
    reservation_id: UUID = Field(description="Identifier of the active slot reservation.")
    driver_name: str = Field(
        min_length=2,
        max_length=100,
        description="Name of the driver responsible for the booking.",
    )
    driver_mobile: str = Field(
        min_length=10,
        max_length=10,
        pattern=r"^[0-9]{10}$",
        description="Driver mobile number in 10 digit format.",
    )
    driver_license: str = Field(
        min_length=6,
        max_length=64,
        description="Driver license number.",
    )


class CreateBookingResponse(BaseModel):
    """Booking summary returned after successful creation."""

    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    booking_number: str
    status: BookingStatus
    total_amount: Decimal


class BookingStatusResponse(BaseModel):
    """Stable response for batch or status endpoints."""

    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    booking_number: str
    status: BookingStatus


class ErrorResponse(BaseModel):
    """Generic error response model used across endpoints."""

    model_config = ConfigDict(extra="forbid")

    detail: str


class BookingQRResponse(BaseModel):
    """Response model for booking QR retrieval endpoint."""

    model_config = ConfigDict(extra="forbid")

    booking_id: UUID
    booking_number: str
    qr_url: str
    expires_at: datetime | None = None
