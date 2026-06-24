"""Async repository boundary for vehicle and driver persistence."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import VehicleDriverPersistenceException
from .models import DriverDetails, VehicleDetails
from .schemas import DriverDetailsRequest, VehicleDetailsRequest


class VehicleDriverRepository(Protocol):
    """Persistence contract consumed by the service layer."""

    async def create_vehicle(
        self,
        *,
        booking_id: UUID,
        vehicle: VehicleDetailsRequest,
        eligibility_status: str,
        warnings: list[str],
        rejections: list[str],
    ) -> VehicleDetails: ...

    async def create_driver(
        self,
        *,
        booking_id: UUID,
        driver: DriverDetailsRequest,
    ) -> DriverDetails: ...

    async def get_vehicle_by_booking_id(
        self, booking_id: UUID
    ) -> VehicleDetails | None: ...

    async def get_driver_by_booking_id(
        self, booking_id: UUID
    ) -> DriverDetails | None: ...

    async def update_vehicle(
        self,
        *,
        booking_id: UUID,
        vehicle: VehicleDetailsRequest,
        eligibility_status: str,
        warnings: list[str],
        rejections: list[str],
    ) -> VehicleDetails: ...

    async def update_driver(
        self,
        *,
        booking_id: UUID,
        driver: DriverDetailsRequest,
    ) -> DriverDetails: ...

    async def get_vehicle_by_booking(self, booking_id: UUID) -> VehicleDetails | None: ...

    async def get_driver_by_booking(self, booking_id: UUID) -> DriverDetails | None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class SQLAlchemyVehicleDriverRepository:
    """SQLAlchemy implementation using one transaction for both records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_vehicle(
        self,
        *,
        booking_id: UUID,
        vehicle: VehicleDetailsRequest,
        eligibility_status: str,
        warnings: list[str],
        rejections: list[str],
    ) -> VehicleDetails:
        """Create a vehicle, resolving a concurrent insert as an update."""
        values = self._vehicle_values(
            vehicle, eligibility_status, warnings, rejections
        )
        try:
            statement = (
                insert(VehicleDetails)
                .values(id=uuid.uuid4(), booking_id=booking_id, **values)
                .on_conflict_do_update(
                    constraint="uq_vehicle_details_booking_id",
                    set_=values,
                )
                .returning(VehicleDetails)
            )
            result = await self._session.execute(statement)
        except SQLAlchemyError as exc:
            raise VehicleDriverPersistenceException(
                "Failed to persist vehicle details"
            ) from exc
        return result.scalar_one()

    async def create_driver(
        self,
        *,
        booking_id: UUID,
        driver: DriverDetailsRequest,
    ) -> DriverDetails:
        """Create a driver, resolving a concurrent insert as an update."""
        values = self._driver_values(driver)
        try:
            statement = (
                insert(DriverDetails)
                .values(id=uuid.uuid4(), booking_id=booking_id, **values)
                .on_conflict_do_update(
                    constraint="uq_driver_details_booking_id",
                    set_=values,
                )
                .returning(DriverDetails)
            )
            result = await self._session.execute(statement)
        except SQLAlchemyError as exc:
            raise VehicleDriverPersistenceException(
                "Failed to persist driver details"
            ) from exc
        return result.scalar_one()

    async def get_vehicle_by_booking_id(
        self, booking_id: UUID
    ) -> VehicleDetails | None:
        """Return the single vehicle record belonging to a booking."""
        try:
            result = await self._session.execute(
                select(VehicleDetails).where(VehicleDetails.booking_id == booking_id)
            )
        except SQLAlchemyError as exc:
            raise VehicleDriverPersistenceException(
                "Failed to query vehicle details"
            ) from exc
        return result.scalar_one_or_none()

    async def get_driver_by_booking_id(
        self, booking_id: UUID
    ) -> DriverDetails | None:
        """Return the single driver record belonging to a booking."""
        try:
            result = await self._session.execute(
                select(DriverDetails).where(DriverDetails.booking_id == booking_id)
            )
        except SQLAlchemyError as exc:
            raise VehicleDriverPersistenceException(
                "Failed to query driver details"
            ) from exc
        return result.scalar_one_or_none()

    async def update_vehicle(
        self,
        *,
        booking_id: UUID,
        vehicle: VehicleDetailsRequest,
        eligibility_status: str,
        warnings: list[str],
        rejections: list[str],
    ) -> VehicleDetails:
        """Update and return the vehicle record for a booking."""
        try:
            result = await self._session.execute(
                update(VehicleDetails)
                .where(VehicleDetails.booking_id == booking_id)
                .values(
                    **self._vehicle_values(
                        vehicle, eligibility_status, warnings, rejections
                    )
                )
                .returning(VehicleDetails)
            )
        except SQLAlchemyError as exc:
            raise VehicleDriverPersistenceException(
                "Failed to update vehicle details"
            ) from exc
        record = result.scalar_one_or_none()
        if record is None:
            raise VehicleDriverPersistenceException("Vehicle record no longer exists")
        return record

    async def update_driver(
        self,
        *,
        booking_id: UUID,
        driver: DriverDetailsRequest,
    ) -> DriverDetails:
        """Update and return the driver record for a booking."""
        try:
            result = await self._session.execute(
                update(DriverDetails)
                .where(DriverDetails.booking_id == booking_id)
                .values(**self._driver_values(driver))
                .returning(DriverDetails)
            )
        except SQLAlchemyError as exc:
            raise VehicleDriverPersistenceException(
                "Failed to update driver details"
            ) from exc
        record = result.scalar_one_or_none()
        if record is None:
            raise VehicleDriverPersistenceException("Driver record no longer exists")
        return record

    async def get_vehicle_by_booking(self, booking_id: UUID) -> VehicleDetails | None:
        """Backward-compatible alias for get_vehicle_by_booking_id."""
        return await self.get_vehicle_by_booking_id(booking_id)

    async def get_driver_by_booking(self, booking_id: UUID) -> DriverDetails | None:
        """Backward-compatible alias for get_driver_by_booking_id."""
        return await self.get_driver_by_booking_id(booking_id)

    @staticmethod
    def _vehicle_values(
        vehicle: VehicleDetailsRequest,
        eligibility_status: str,
        warnings: list[str],
        rejections: list[str],
    ) -> dict[str, object]:
        """Build the shared vehicle insert/update values."""
        return {
            "registration_number": vehicle.registration_number,
            "vehicle_type": vehicle.vehicle_type,
            "gvw_tonnes": vehicle.gvw_tonnes,
            "height_m": vehicle.height_m,
            "length_m": vehicle.length_m,
            "width_m": vehicle.width_m,
            "eligibility_status": eligibility_status,
            "warnings": list(warnings),
            "rejections": list(rejections),
        }

    @staticmethod
    def _driver_values(driver: DriverDetailsRequest) -> dict[str, object]:
        """Build the shared driver insert/update values."""
        return {
            "driver_name": driver.name,
            "mobile_number": driver.mobile_number,
            "licence_number": driver.licence_number,
            "accompanying": driver.accompanying,
        }

    async def commit(self) -> None:
        """Commit the vehicle and driver records together."""
        try:
            await self._session.commit()
        except SQLAlchemyError as exc:
            raise VehicleDriverPersistenceException(
                "Failed to commit vehicle and driver details"
            ) from exc

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        await self._session.rollback()
