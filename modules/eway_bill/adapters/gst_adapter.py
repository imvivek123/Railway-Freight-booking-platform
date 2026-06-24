"""Gateway abstraction for the GST E-Way Bill service."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GSTAdapterError(RuntimeError):
    """Raised when the upstream GST provider cannot complete a lookup."""


class GSTAdapter(ABC):
    """Interface implemented by GST provider integrations."""

    @abstractmethod
    async def fetch_eway_bill(self, eway_bill_number: str) -> dict[str, Any]:
        """Fetch raw E-Way Bill data from a GST provider."""
        raise NotImplementedError


class MockGSTAdapter(GSTAdapter):
    """Deterministic development adapter that performs no network access."""

    async def fetch_eway_bill(self, eway_bill_number: str) -> dict[str, Any]:
        """Return representative GST data for the requested bill number."""
        return {
            "ewayBillNo": eway_bill_number,
            "fromTrdName": "ABC Industries",
            "fromGstin": "09ABCDE1234F1Z5",
            "toTrdName": "XYZ Logistics",
            "toGstin": "27ABCDE1234F1Z5",
            "prodDesc": "Steel Rods",
            "hsnCode": "7214",
            "quantity": 100,
            "qtyUnit": "KG",
            "taxableAmount": 250000,
            "vehNo": "HR38AB1234",
            "validUpto": "2026-06-30T23:59:59",
        }

