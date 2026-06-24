"""Booking confirmation QR service skeleton."""


class QRService:
    """QR generation service for booking confirmations.

    Full implementation will be added later.
    """

    async def generate_qr(
        self,
        booking_id: str,
        vehicle_reg: str,
        departure_iso: str,
    ) -> None:
        """Generate a booking QR payload in a future implementation."""
        pass

    async def validate_qr(
        self,
        qr_payload: str,
    ) -> None:
        """Validate a booking QR payload in a future implementation."""
        pass

