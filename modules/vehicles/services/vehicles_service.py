"""Vehicle eligibility and driver validation application service."""

from __future__ import annotations

import logging
from time import perf_counter

from ..constants import CONDITIONAL, DRIVER_VALID, ELIGIBLE, REJECTED
from ..repository import VehicleDriverRepository
from ..schemas import (
    DriverDetailsRequest,
    VehicleDetailsRequest,
    VehicleDriverSaveRequest,
    VehicleDriverSaveResponse,
)
from ..validators import (
    validate_driver_name,
    validate_licence_number,
    validate_mobile_number,
)
from .eligibility import (
    validate_vehicle_height,
    validate_vehicle_length,
    validate_vehicle_weight,
    validate_vehicle_width,
)

logger = logging.getLogger(__name__)


class VehicleDriverService:
    """Validate and atomically persist vehicle and driver booking data."""

    def __init__(self, repository: VehicleDriverRepository) -> None:
        self._repository = repository

    def validate_vehicle(
        self, vehicle: VehicleDetailsRequest
    ) -> tuple[list[str], list[str]]:
        """Apply all vehicle rules and aggregate warnings and rejections."""
        warnings: list[str] = []
        rejections: list[str] = []
        for validator, value in (
            (validate_vehicle_height, vehicle.height_m),
            (validate_vehicle_length, vehicle.length_m),
            (validate_vehicle_width, vehicle.width_m),
            (validate_vehicle_weight, vehicle.gvw_tonnes),
        ):
            new_warnings, new_rejections = validator(value)
            warnings.extend(new_warnings)
            rejections.extend(new_rejections)
        return warnings, rejections

    def validate_driver(self, driver: DriverDetailsRequest) -> DriverDetailsRequest:
        """Validate and normalize local driver data without an external API."""
        return driver.model_copy(
            update={
                "name": validate_driver_name(driver.name),
                "mobile_number": validate_mobile_number(driver.mobile_number),
                "licence_number": validate_licence_number(driver.licence_number),
            }
        )

    def determine_vehicle_status(
        self, warnings: list[str], rejections: list[str]
    ) -> str:
        """Resolve rejection before conditional review, then eligibility."""
        if rejections:
            return REJECTED
        if warnings:
            return CONDITIONAL
        return ELIGIBLE

    async def persist_vehicle(
        self,
        request: VehicleDriverSaveRequest,
        vehicle_status: str,
        warnings: list[str],
        rejections: list[str],
    ) -> None:
        """Create or update the booking's single vehicle record."""
        existing_vehicle = await self._repository.get_vehicle_by_booking_id(
            request.booking_id
        )
        values = {
            "booking_id": request.booking_id,
            "vehicle": request.vehicle,
            "eligibility_status": vehicle_status,
            "warnings": warnings,
            "rejections": rejections,
        }
        if existing_vehicle is None:
            logger.info(
                "Creating vehicle record booking_id=%s registration_number=%s",
                request.booking_id,
                request.vehicle.registration_number,
            )
            await self._repository.create_vehicle(**values)
        else:
            logger.info(
                "Updating vehicle record booking_id=%s registration_number=%s",
                request.booking_id,
                request.vehicle.registration_number,
            )
            await self._repository.update_vehicle(**values)

    async def persist_driver(
        self, request: VehicleDriverSaveRequest, driver: DriverDetailsRequest
    ) -> None:
        """Create or update the booking's single driver record."""
        existing_driver = await self._repository.get_driver_by_booking_id(
            request.booking_id
        )
        if existing_driver is None:
            logger.info(
                "Creating driver record booking_id=%s driver_name=%s",
                request.booking_id,
                driver.name,
            )
            await self._repository.create_driver(
                booking_id=request.booking_id, driver=driver
            )
        else:
            logger.info(
                "Updating driver record booking_id=%s driver_name=%s",
                request.booking_id,
                driver.name,
            )
            await self._repository.update_driver(
                booking_id=request.booking_id, driver=driver
            )

    def build_response(
        self,
        vehicle_status: str,
        warnings: list[str],
        rejections: list[str],
    ) -> VehicleDriverSaveResponse:
        """Build the stable API response contract."""
        return VehicleDriverSaveResponse(
            status=vehicle_status,
            vehicle_status=vehicle_status,
            driver_status=DRIVER_VALID,
            warnings=warnings,
            rejections=rejections,
        )

    async def save(
        self, request: VehicleDriverSaveRequest
    ) -> VehicleDriverSaveResponse:
        """Validate and atomically persist a vehicle-driver submission."""
        started_at = perf_counter()
        vehicle_status = "INVALID"
        try:
            warnings, rejections = self.validate_vehicle(request.vehicle)
            driver = self.validate_driver(request.driver)
            vehicle_status = self.determine_vehicle_status(warnings, rejections)
            await self.persist_vehicle(
                request, vehicle_status, warnings, rejections
            )
            await self.persist_driver(request, driver)
            await self._repository.commit()
            return self.build_response(vehicle_status, warnings, rejections)
        except Exception:
            await self._repository.rollback()
            raise
        finally:
            logger.info(
                "Vehicle-driver save booking_id=%s registration_number=%s "
                "driver_name=%s vehicle_status=%s execution_time_ms=%.2f",
                request.booking_id,
                request.vehicle.registration_number,
                request.driver.name,
                vehicle_status,
                (perf_counter() - started_at) * 1000,
            )
