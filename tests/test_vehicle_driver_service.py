"""Unit tests for vehicle-driver validation and persistence orchestration."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import pytest

from modules.vehicles.exceptions import InvalidDriverDataException
from modules.vehicles.schemas import (
    DriverDetailsRequest,
    VehicleDetailsRequest,
    VehicleDriverSaveRequest,
)
from modules.vehicles.services.vehicles_service import VehicleDriverService


class FakeRepository:
    """In-memory repository spy used by service unit tests."""

    def __init__(self) -> None:
        self.vehicles: dict[UUID, dict[str, Any]] = {}
        self.drivers: dict[UUID, dict[str, Any]] = {}
        self.vehicle_creates = 0
        self.vehicle_updates = 0
        self.driver_creates = 0
        self.driver_updates = 0
        self.committed = False
        self.rolled_back = False

    async def create_vehicle(self, **values: Any) -> Any:
        self.vehicle_creates += 1
        self.vehicles[values["booking_id"]] = values
        return values

    async def create_driver(self, **values: Any) -> Any:
        self.driver_creates += 1
        self.drivers[values["booking_id"]] = values
        return values

    async def get_vehicle_by_booking_id(self, booking_id: UUID) -> Any:
        return self.vehicles.get(booking_id)

    async def get_driver_by_booking_id(self, booking_id: UUID) -> Any:
        return self.drivers.get(booking_id)

    async def get_vehicle_by_booking(self, booking_id: UUID) -> Any:
        return await self.get_vehicle_by_booking_id(booking_id)

    async def get_driver_by_booking(self, booking_id: UUID) -> Any:
        return await self.get_driver_by_booking_id(booking_id)

    async def update_vehicle(self, **values: Any) -> Any:
        self.vehicle_updates += 1
        self.vehicles[values["booking_id"]] = values
        return values

    async def update_driver(self, **values: Any) -> Any:
        self.driver_updates += 1
        self.drivers[values["booking_id"]] = values
        return values

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


def make_request(
    *,
    height_m: float = 3.2,
    gvw_tonnes: float = 22.5,
    mobile_number: str = "9876543210",
    driver_name: str = "Suresh Kumar Yadav",
    registration_number: str = "HR55AE7821",
    booking_id: UUID = UUID("123e4567-e89b-12d3-a456-426614174000"),
) -> VehicleDriverSaveRequest:
    """Build a valid request with selected rule overrides."""
    return VehicleDriverSaveRequest(
        booking_id=booking_id,
        vehicle=VehicleDetailsRequest(
            registration_number=registration_number,
            vehicle_type="20ft Container Trailer",
            gvw_tonnes=gvw_tonnes,
            height_m=height_m,
            length_m=9.14,
            width_m=2.44,
        ),
        driver=DriverDetailsRequest(
            name=driver_name,
            mobile_number=mobile_number,
            licence_number="HR0520150012345",
            accompanying=True,
        ),
    )


def run_save(
    request: VehicleDriverSaveRequest,
) -> tuple[Any, FakeRepository]:
    """Execute the async service without requiring a pytest async plugin."""
    repository = FakeRepository()
    result = asyncio.run(VehicleDriverService(repository).save(request))
    return result, repository


def test_eligible_vehicle() -> None:
    result, _ = run_save(make_request())
    assert result.status == "ELIGIBLE"
    assert result.warnings == []
    assert result.rejections == []


def test_conditional_vehicle() -> None:
    result, _ = run_save(make_request(height_m=3.5, gvw_tonnes=35))
    assert result.status == "CONDITIONAL"
    assert result.warnings == [
        "Vehicle height exceeds preferred limit",
        "Vehicle weight requires manual review",
    ]


def test_rejected_vehicle() -> None:
    result, _ = run_save(make_request(height_m=3.81))
    assert result.status == "REJECTED"
    assert result.rejections == ["Vehicle height exceeds maximum limit"]


def test_invalid_mobile() -> None:
    with pytest.raises(InvalidDriverDataException, match="Invalid mobile number"):
        run_save(make_request(mobile_number="98765"))


def test_invalid_driver_name() -> None:
    with pytest.raises(InvalidDriverDataException, match="Invalid driver name"):
        run_save(make_request(driver_name="S"))


def test_successful_persistence() -> None:
    result, repository = run_save(make_request())
    assert result.driver_status == "VALID"
    assert repository.committed is True
    assert repository.rolled_back is False
    assert len(repository.vehicles) == 1
    assert len(repository.drivers) == 1
    booking_id = next(iter(repository.vehicles))
    assert booking_id in repository.drivers


def test_first_request_creates_records() -> None:
    repository = FakeRepository()
    asyncio.run(VehicleDriverService(repository).save(make_request()))
    assert repository.vehicle_creates == 1
    assert repository.driver_creates == 1
    assert repository.vehicle_updates == 0
    assert repository.driver_updates == 0


def test_second_request_with_same_booking_updates_records() -> None:
    repository = FakeRepository()
    service = VehicleDriverService(repository)
    asyncio.run(service.save(make_request()))
    asyncio.run(
        service.save(
            make_request(
                registration_number="HR55AE9999",
                driver_name="Updated Driver",
            )
        )
    )
    assert repository.vehicle_creates == 1
    assert repository.driver_creates == 1
    assert repository.vehicle_updates == 1
    assert repository.driver_updates == 1


def test_row_count_remains_one_for_same_booking() -> None:
    repository = FakeRepository()
    service = VehicleDriverService(repository)
    asyncio.run(service.save(make_request()))
    asyncio.run(
        service.save(
            make_request(
                registration_number="HR55AE9999",
                driver_name="Updated Driver",
            )
        )
    )
    assert len(repository.vehicles) == 1
    assert len(repository.drivers) == 1
    booking_id = UUID("123e4567-e89b-12d3-a456-426614174000")
    assert repository.vehicles[booking_id]["vehicle"].registration_number == "HR55AE9999"
    assert repository.drivers[booking_id]["driver"].name == "Updated Driver"
