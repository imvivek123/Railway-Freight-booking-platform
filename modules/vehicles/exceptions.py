"""Domain and persistence exceptions for vehicle and driver onboarding."""


class VehicleDriverException(RuntimeError):
    """Base exception for the vehicle-driver module."""


class InvalidVehicleDataException(VehicleDriverException):
    """Raised when vehicle data is missing, non-positive, or otherwise invalid."""


class InvalidDriverDataException(VehicleDriverException):
    """Raised when driver details do not satisfy local validation rules."""


class VehicleRejectedException(VehicleDriverException):
    """Raised by callers that require an eligible vehicle to continue."""


class VehicleDriverPersistenceException(VehicleDriverException):
    """Raised when vehicle or driver persistence fails."""

