"""Placeholder client boundary for the future NIC GST integration."""

from __future__ import annotations

from typing import Any


class GSTAPIClient:
    """Future async client for the NIC E-Way Bill API.

    Authentication, transport, retries, and payload mapping will be added when
    the NIC integration contract is available.
    """

    async def fetch_eway_bill(self, eway_bill_number: str) -> dict[str, Any]:
        """Fetch an E-Way Bill from NIC once the integration is implemented."""
        raise NotImplementedError("NIC GST API integration is not implemented")

