"""Pydantic v2 API contracts for vehicle and driver onboarding."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VehicleDetailsRequest(BaseModel):
    """Vehicle data used for railway transport eligibility checks."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    registration_number: str = Field(min_length=1, max_length=32)
    vehicle_type: str = Field(min_length=1, max_length=100)
    gvw_tonnes: float
    height_m: float
    length_m: float
    width_m: float


class DriverDetailsRequest(BaseModel):
    """Driver details persisted for a booking."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str
    mobile_number: str
    licence_number: str
    accompanying: bool


class VehicleDriverSaveRequest(BaseModel):
    """Complete vehicle and driver payload for one booking."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "booking_id": "123e4567-e89b-12d3-a456-426614174000",
                    "vehicle": {
                        "registration_number": "HR55AE7821",
                        "vehicle_type": "20ft Container Trailer",
                        "gvw_tonnes": 22.5,
                        "height_m": 3.2,
                        "length_m": 9.14,
                        "width_m": 2.44,
                    },
                    "driver": {
                        "name": "Suresh Kumar Yadav",
                        "mobile_number": "9876543210",
                        "licence_number": "HR0520150012345",
                        "accompanying": True,
                    },
                }
            ]
        },
    )

    booking_id: UUID
    vehicle: VehicleDetailsRequest
    driver: DriverDetailsRequest


class VehicleDriverSaveResponse(BaseModel):
    """Eligibility decision returned before the payment step."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "status": "ELIGIBLE",
                    "vehicle_status": "ELIGIBLE",
                    "driver_status": "VALID",
                    "warnings": [],
                    "rejections": [],
                }
            ]
        },
    )

    status: Literal["ELIGIBLE", "CONDITIONAL", "REJECTED"]
    vehicle_status: Literal["ELIGIBLE", "CONDITIONAL", "REJECTED"]
    driver_status: Literal["VALID"]
    warnings: list[str] = Field(default_factory=list)
    rejections: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Standard error response for this API."""

    detail: object

