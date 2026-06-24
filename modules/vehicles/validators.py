"""Pure validation functions for driver identity."""

from __future__ import annotations

from .exceptions import InvalidDriverDataException


def validate_driver_name(name: str) -> str:
    """Normalize and validate the driver's required name."""
    normalized = name.strip()
    if len(normalized) < 2:
        raise InvalidDriverDataException("Invalid driver name")
    return normalized


def validate_mobile_number(mobile_number: str) -> str:
    """Require exactly ten ASCII digits."""
    normalized = mobile_number.strip()
    if (
        len(normalized) != 10
        or not normalized.isascii()
        or not normalized.isdigit()
    ):
        raise InvalidDriverDataException("Invalid mobile number")
    return normalized


def validate_licence_number(licence_number: str) -> str:
    """Require non-empty free text without external government validation."""
    normalized = licence_number.strip()
    if not normalized:
        raise InvalidDriverDataException("Invalid licence number")
    return normalized
