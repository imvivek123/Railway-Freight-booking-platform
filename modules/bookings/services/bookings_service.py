from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ..enums import BookingStatus
from ..exceptions import (
    BookingAccessDeniedException,
    BookingNotFoundException,
    BookingException,
    InvalidBookingStateTransitionException,
    InvalidEwayBillException,
    ReservationExpiredException,
    VehicleNotEligibleException,
    VehicleNotFoundException,
)
from ..repository import BookingsRepository, BookingsRepositoryError
from ..schemas import (
    CreateBookingRequest,
    CreateBookingResponse,
    BookingStatusResponse,
    BookingQRResponse,
)
from datetime import timedelta

logger = logging.getLogger(__name__)

VALID_TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    BookingStatus.RESERVED: {BookingStatus.CONFIRMED, BookingStatus.PAYMENT_FAILED},
    BookingStatus.CONFIRMED: {BookingStatus.CANCELLED},
    BookingStatus.GATE_ENTRY: {BookingStatus.LOADED},
    BookingStatus.LOADED: {BookingStatus.IN_TRANSIT},
    BookingStatus.IN_TRANSIT: {BookingStatus.ARRIVED},
    BookingStatus.ARRIVED: {BookingStatus.UNLOADED, BookingStatus.NO_SHOW},
}

BOOKING_NUMBER_SEQUENCE_KEY = "booking_number_sequence"


def generate_booking_number(counter: int, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    padded = f"{counter:06d}"
    return f"RR-BKG-{now:%Y%m%d}-{padded}"


class BookingsService:
    """Business orchestration for booking creation and lifecycle transitions."""

    def __init__(
        self,
        repository: BookingsRepository,
        session: AsyncSession,
        reservation_service: Any,
        eway_bill_service: Any,
        vehicles_service: Any,
        pricing_service: Any,
        current_datetime: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._session = session
        self._reservation_service = reservation_service
        self._eway_bill_service = eway_bill_service
        self._vehicles_service = vehicles_service
        self._pricing_service = pricing_service
        self._clock = current_datetime or datetime.utcnow

    async def _generate_unique_booking_number(self) -> str:
        try:
            result = await self._session.execute(select(func.nextval(BOOKING_NUMBER_SEQUENCE_KEY)))
            counter = result.scalar_one()
        except Exception as exc:
            logger.exception("Booking number sequence fetch failed")
            raise BookingNotFoundException(
                "Unable to generate booking number at this time"
            ) from exc
        return generate_booking_number(counter, self._clock())

    async def create_booking(
        self,
        request: CreateBookingRequest,
        user_id: UUID,
    ) -> CreateBookingResponse:
        logger.info(
            "Booking creation started",
            extra={
                "user_id": str(user_id),
                "reservation_id": str(request.reservation_id),
                "eway_bill_number": request.eway_bill_number,
                "vehicle_id": str(request.vehicle_id),
            },
        )
# from here i will extract the usser details and validate the booking request
# here after i am  checking the reservation and eway bill details and validating the vehicle eligibility and pricing
        reservation = await self._reservation_service.get_active_reservation(
            request.reservation_id
        )
        if reservation is None:
            logger.warning(
                "Reservation verification failed",
                extra={"reservation_id": str(request.reservation_id)},
            )
            raise ReservationExpiredException(
                "Active reservation not found or has expired"
            )
        logger.info(
            "Reservation verified",
            extra={"reservation_id": str(request.reservation_id)},
        )

        eway_response = await self._eway_bill_service.get_cached_bill(
            request.eway_bill_number
        )
        if eway_response is None or getattr(eway_response, "status", "") != "ALLOW":
            logger.warning(
                "E-Way Bill validation failed",
                extra={"eway_bill_number": request.eway_bill_number},
            )
            raise InvalidEwayBillException(
                "E-Way Bill is invalid, expired, or not allowed for this booking"
            )
        logger.info(
            "E-Way Bill verified",
            extra={"eway_bill_number": request.eway_bill_number},
        )

        vehicle = await self._vehicles_service.get_vehicle(request.vehicle_id)
        if vehicle is None:
            logger.warning(
                "Vehicle lookup failed",
                extra={"vehicle_id": str(request.vehicle_id)},
            )
            raise VehicleNotFoundException(
                "Requested vehicle does not exist"
            )
        logger.info(
            "Vehicle verified",
            extra={"vehicle_id": str(request.vehicle_id)},
        )

        is_eligible = await self._vehicles_service.run_eligibility_check(vehicle)
        if not is_eligible:
            logger.warning(
                "Vehicle eligibility failed",
                extra={"vehicle_id": str(request.vehicle_id)},
            )
            raise VehicleNotEligibleException(
                "Vehicle does not meet eligibility requirements"
            )
        logger.info(
            "Vehicle eligibility passed",
            extra={"vehicle_id": str(request.vehicle_id)},
        )

        pricing_response = await self._pricing_service.calculate_booking_price(
            route_id=reservation.route_id,
            vehicle=vehicle,
        )
        if pricing_response is None:
            logger.warning(
                "Pricing calculation failed",
                extra={
                    "reservation_id": str(request.reservation_id),
                    "vehicle_id": str(request.vehicle_id),
                },
            )
            raise BookingNotFoundException(
                "Unable to calculate booking price"
            )
        logger.info(
            "Pricing calculated",
            extra={
                "reservation_id": str(request.reservation_id),
                "vehicle_id": str(request.vehicle_id),
                "total_amount": str(pricing_response["total"]),
            },
        )

        booking_number = await self._generate_unique_booking_number()
#what this part does- is that it generates a unique booking number for the new booking by calling the `_generate_unique_booking_number` method. 
# This method retrieves the next value from a sequence in the database (using `func.nextval`) and formats it into a string that includes the current date and a padded counter. 
# The generated booking number is then used when creating the booking record in the database.
        try:
            async with self._session.begin():
                booking = await self._repository.create_booking(
                    booking_number=booking_number,
                    user_id=user_id,
                    vehicle_id=request.vehicle_id,
                    reservation_id=request.reservation_id,
                    status=BookingStatus.RESERVED,
                    eway_bill_data=eway_response.eway_data,
                    price_snapshot=pricing_response,
                    driver_name=request.driver_name,
                    driver_mobile=request.driver_mobile,
                    driver_license=request.driver_license,
                    total_amount=Decimal(str(pricing_response["total"])),
                )
        except BookingsRepositoryError as exc:
            logger.exception("Booking persistence failed")
            raise BookingNotFoundException(
                "Unable to save booking at this time"
            ) from exc
        except SQLAlchemyError as exc:
            logger.exception("Booking transaction failed")
            raise BookingNotFoundException(
                "Unable to save booking at this time"
            ) from exc

        logger.info(
            "Booking created",
            extra={
                "booking_id": str(booking.id),
                "booking_number": booking.booking_number,
                "status": booking.status,
            },
        )

        return CreateBookingResponse(
            booking_id=booking.id,
            booking_number=booking.booking_number,
            status=BookingStatus(booking.status),
            total_amount=booking.total_amount,
        )
#what this part does- is that it attempts to create a new booking record in the database using the validated data and the generated booking number.
    async def get_booking(self, booking_id: UUID, current_user: Any) -> BookingStatusResponse:
        booking = await self._repository.get_by_id(booking_id)
        if booking is None:
            raise BookingNotFoundException("Booking not found")
        if not self._is_access_allowed(booking, current_user):
            raise BookingAccessDeniedException("Booking not accessible")
        return BookingStatusResponse(
            booking_id=booking.id,
            booking_number=booking.booking_number,
            status=BookingStatus(booking.status),
        )

    async def get_booking_status(self, booking_id: UUID, current_user: Any) -> BookingStatusResponse:
        return await self.get_booking(booking_id, current_user)

    async def list_user_bookings(self, current_user: Any) -> list[BookingStatusResponse]:
        if self._is_admin(current_user):
            bookings = await self._repository.list_user_bookings(None)
        else:
            bookings = await self._repository.list_user_bookings(current_user.id)
        return [
            BookingStatusResponse(
                booking_id=booking.id,
                booking_number=booking.booking_number,
                status=BookingStatus(booking.status),
            )
            for booking in bookings
        ]
#what this part does- is that it retrieves a list of bookings for the current user. If the user is an admin, it fetches all bookings; otherwise, it fetches only the bookings associated with the user's ID. The method returns a list of `BookingStatusResponse` objects, each containing the booking ID, booking number, and status.
    async def transition_state(
        self, booking_id: UUID, target_status: BookingStatus, current_user: Any
    ) -> BookingStatusResponse:
        booking = await self._repository.get_by_id(booking_id)
        if booking is None:
            raise BookingNotFoundException("Booking not found")
        if not self._is_access_allowed(booking, current_user):
            raise BookingNotFoundException("Booking not accessible")

        current_status = BookingStatus(booking.status)
        allowed = VALID_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            raise InvalidBookingStateTransitionException(
                f"Invalid booking transition from {current_status.value} to {target_status.value}"
            )
#
        updated = await self._repository.update_booking_status(booking_id, target_status)
        return BookingStatusResponse(
            booking_id=updated.id,
            booking_number=updated.booking_number,
            status=BookingStatus(updated.status),
        )

    def _is_admin(self, current_user: Any) -> bool:
        return getattr(current_user, "is_admin", False) or getattr(current_user, "role", "") == "ADMIN"

    def _is_access_allowed(self, booking: Any, current_user: Any) -> bool:
        if self._is_admin(current_user):
            return True
        return booking.user_id == getattr(current_user, "id", None)

    async def get_booking_qr(
        self,
        booking_id: UUID,
        current_user: Any,
        qr_service: Any,
        presign_seconds: int = 3600,
    ) -> BookingQRResponse:
        """Return QR URL (presigned) for a booking.

        This method orchestrates fetching the booking, validating access,
        delegating QR generation to `QRService`, uploading the image, and
        returning a presigned URL if available.
        """
        booking = await self._repository.get_by_id(booking_id)
        if booking is None:
            raise BookingNotFoundException("Booking not found")
        if not self._is_access_allowed(booking, current_user):
            raise BookingAccessDeniedException("Booking not accessible")

        # Resolve vehicle registration (best-effort)
        vehicle_reg = None
        try:
            vehicle = await self._vehicles_service.get_vehicle(booking.vehicle_id)
            if vehicle is not None:
                vehicle_reg = getattr(vehicle, "registration_number", None) or getattr(
                    vehicle, "registration", None
                )
                if vehicle_reg is None and isinstance(vehicle, dict):
                    vehicle_reg = vehicle.get("registration_number") or vehicle.get("registration")
        except Exception:
            vehicle_reg = None

        if not vehicle_reg:
            vehicle_reg = str(booking.vehicle_id)

        # Resolve departure timestamp (best-effort)
        departure_iso = None
        try:
            # Try common reservation accessors (best-effort)
            if hasattr(self._reservation_service, "get_reservation"):
                reservation = await self._reservation_service.get_reservation(
                    booking.reservation_id
                )
            else:
                reservation = await self._reservation_service.get_active_reservation(
                    booking.reservation_id
                )
            if reservation is not None:
                departure_iso = getattr(reservation, "departure_iso", None) or getattr(
                    reservation, "departure_time", None
                )
        except Exception:
            departure_iso = None

        if not departure_iso:
            # Fallback to booking created timestamp
            try:
                departure_iso = booking.created_at.isoformat()
            except Exception:
                departure_iso = datetime.utcnow().isoformat()

        # Delegate QR generation to QRService
        qr_result = await qr_service.generate_qr(
            booking.booking_number, vehicle_reg, departure_iso
        )

        qr_image = qr_result.get("qr_image")
        # Upload image (placeholder implementation may return a direct URL)
        storage_url = await qr_service.upload_qr_to_storage(booking.booking_number, qr_image)

        # Prefer presigned URL when available
        presigned_url = None
        try:
            presigned_url = await qr_service.generate_presigned_url(
                booking.booking_number, expiration_seconds=presign_seconds
            )
        except TypeError:
            # Backwards compatibility if arg name differs
            presigned_url = await qr_service.generate_presigned_url(
                booking.booking_number, presign_seconds
            )
        except Exception:
            presigned_url = None

        qr_url = presigned_url or storage_url
        expires_at = None
        if presigned_url:
            expires_at = datetime.utcnow() + timedelta(seconds=presign_seconds)

        return BookingQRResponse(
            booking_id=booking.id,
            booking_number=booking.booking_number,
            qr_url=qr_url,
            expires_at=expires_at,
        )
