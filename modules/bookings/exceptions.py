from __future__ import annotations


class BookingException(RuntimeError):
    """Base exception for booking operations."""


class ReservationExpiredException(BookingException):
    """Raised when an active reservation cannot be found or has expired."""


class InvalidEwayBillException(BookingException):
    """Raised when the requested E-Way Bill is invalid or unavailable."""


class VehicleNotFoundException(BookingException):
    """Raised when the requested vehicle does not exist."""


class VehicleNotEligibleException(BookingException):
    """Raised when a vehicle fails eligibility verification."""


class BookingNotFoundException(BookingException):
    """Raised when a booking cannot be located for the current user."""


class BookingAccessDeniedException(BookingException):
    """Raised when the current user cannot access the requested booking."""


class InvalidBookingStateTransitionException(BookingException):
    """Raised when a booking transition is not allowed by business rules."""
