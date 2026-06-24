"""Pure validation functions for vehicle eligibility."""

from __future__ import annotations

import math

from ..constants import (
    GVW_REVIEW_MIN_TONNES,
    HEIGHT_REJECTION,
    HEIGHT_REVIEW_MIN_M,
    HEIGHT_WARNING,
    LENGTH_REJECTION,
    MAX_GVW_TONNES,
    MAX_HEIGHT_M,
    MAX_LENGTH_M,
    MAX_WIDTH_M,
    WEIGHT_REJECTION,
    WEIGHT_WARNING,
    WIDTH_REJECTION,
)
from ..exceptions import InvalidVehicleDataException

ValidationMessages = tuple[list[str], list[str]]


def _require_positive_dimension(value: float) -> None:
    """Require a finite positive vehicle measurement."""
    if not math.isfinite(value) or value <= 0:
        raise InvalidVehicleDataException("Invalid vehicle dimensions")


def validate_vehicle_height(height_m: float) -> ValidationMessages:
    """Return height warnings and rejections."""
    _require_positive_dimension(height_m)
    if height_m > MAX_HEIGHT_M:
        return [], [HEIGHT_REJECTION]
    if height_m >= HEIGHT_REVIEW_MIN_M:
        return [HEIGHT_WARNING], []
    return [], []


def validate_vehicle_length(length_m: float) -> ValidationMessages:
    """Return length warnings and rejections."""
    _require_positive_dimension(length_m)
    return ([], [LENGTH_REJECTION]) if length_m > MAX_LENGTH_M else ([], [])


def validate_vehicle_width(width_m: float) -> ValidationMessages:
    """Return width warnings and rejections."""
    _require_positive_dimension(width_m)
    return ([], [WIDTH_REJECTION]) if width_m > MAX_WIDTH_M else ([], [])


def validate_vehicle_weight(gvw_tonnes: float) -> ValidationMessages:
    """Return gross-weight warnings and rejections."""
    _require_positive_dimension(gvw_tonnes)
    if gvw_tonnes > MAX_GVW_TONNES:
        return [], [WEIGHT_REJECTION]
    if gvw_tonnes >= GVW_REVIEW_MIN_TONNES:
        return [WEIGHT_WARNING], []
    return [], []

__all__ = [
    "validate_vehicle_height",
    "validate_vehicle_length",
    "validate_vehicle_weight",
    "validate_vehicle_width",
]
