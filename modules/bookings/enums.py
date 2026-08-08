from __future__ import annotations

from enum import Enum


class BookingStatus(str, Enum):
    RESERVED = "RESERVED"
    CONFIRMED = "CONFIRMED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    CANCELLED = "CANCELLED"
    GATE_ENTRY = "GATE_ENTRY"
    LOADED = "LOADED"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVED = "ARRIVED"
    UNLOADED = "UNLOADED"
    NO_SHOW = "NO_SHOW"
