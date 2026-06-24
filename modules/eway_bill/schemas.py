"""Pydantic contracts for the E-Way Bill API."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EWayBillFetchRequest(BaseModel):
    """Input required to verify an E-Way Bill for a booking."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    booking_id: UUID
    eway_bill_number: str = Field(
        description="The exact 12-digit GST E-Way Bill number",
        examples=["181012345678"],
    )

    @field_validator("eway_bill_number")
    @classmethod
    def validate_eway_bill_number(cls, value: str) -> str:
        """Reject values that are not exactly twelve ASCII digits."""
        if len(value) != 12 or not value.isascii() or not value.isdigit():
            raise ValueError("eway_bill_number must contain exactly 12 digits")
        return value


class EWayBillFetchResponse(BaseModel):
    """Business decision and source data returned by an E-Way Bill lookup."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ALLOW", "REJECT"]
    validity_hours_remaining: int
    warnings: list[str] = Field(default_factory=list)
    eway_data: dict[str, Any]


class ErrorResponse(BaseModel):
    """Standard HTTP error body exposed by this module."""

    detail: Any
