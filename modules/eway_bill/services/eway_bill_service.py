"""Business rules and orchestration for E-Way Bill verification."""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from ..adapters.gst_adapter import GSTAdapter, GSTAdapterError
from ..repository import EWayBillRepository
from ..schemas import EWayBillFetchRequest, EWayBillFetchResponse

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 15 * 60
EXPIRY_WARNING_HOURS = 48
EXPIRY_WARNING = "E-Way Bill expires in less than 48 hours"
RESTRICTED_COMMODITIES = frozenset(
    {
        "explosives",
        "fireworks",
        "radioactive_materials",
        "livestock",
        "petroleum_crude",
        "hazardous_chemicals_class_1",
    }
)


class AsyncCache(Protocol):
    """Minimal async cache contract required by the service."""

    async def get(self, key: str) -> bytes | str | None:
        """Return a cached value, if present."""
        ...

    async def set(self, key: str, value: str, *, ex: int) -> Any:
        """Store a value with a TTL in seconds."""
        ...

    async def delete(self, key: str) -> Any:
        """Delete a cache entry."""
        ...


class GSTServiceUnavailableError(RuntimeError):
    """Raised when GST data cannot be obtained from the upstream provider."""


class InvalidGSTResponseError(RuntimeError):
    """Raised when the GST provider returns an unusable payload."""


class EWayBillService:
    """Coordinates caching, GST lookup, validation, and persistence."""

    def __init__(
        self,
        *,
        repository: EWayBillRepository,
        cache: AsyncCache,
        gst_adapter: GSTAdapter,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._cache = cache
        self._gst_adapter = gst_adapter
        self._clock = clock or (lambda: datetime.now(UTC))

    async def fetch(self, request: EWayBillFetchRequest) -> EWayBillFetchResponse:
        """Fetch and evaluate an E-Way Bill, using cache when possible."""
        cache_key = f"eway:{request.eway_bill_number}"
        cached = await self._read_cache(cache_key)
        if cached is not None:
            logger.info(
                "E-Way Bill cache hit", extra={"eway_bill_number": request.eway_bill_number}
            )
            return cached

        try:
            raw_response = await self._gst_adapter.fetch_eway_bill(
                request.eway_bill_number
            )
        except GSTAdapterError as exc:
            logger.warning(
                "GST adapter lookup failed",
                extra={"eway_bill_number": request.eway_bill_number},
                exc_info=True,
            )
            raise GSTServiceUnavailableError("GST service is unavailable") from exc
        except Exception as exc:
            logger.exception(
                "Unexpected GST adapter failure",
                extra={"eway_bill_number": request.eway_bill_number},
            )
            raise GSTServiceUnavailableError("GST service is unavailable") from exc

        validity = self._parse_validity(raw_response)
        now = self._utc(self._clock())
        validity_hours_remaining = math.floor(
            (validity - now).total_seconds() / 3600
        )
        commodity = self._extract_commodity(raw_response)
        status = (
            "REJECT"
            if validity < now or commodity in RESTRICTED_COMMODITIES
            else "ALLOW"
        )
        warnings = []
        if 0 < validity_hours_remaining < EXPIRY_WARNING_HOURS:
            warnings.append(EXPIRY_WARNING)
            
        response = EWayBillFetchResponse(
            status=status,
            validity_hours_remaining=validity_hours_remaining,
            warnings=warnings,
            eway_data=raw_response,
        )

        await self._repository.create(
            booking_id=request.booking_id,
            eway_bill_number=request.eway_bill_number,
            status=response.status,
            validity=validity,
            raw_response=raw_response,
        )
        await self._write_cache(cache_key, response)
        logger.info(
            "E-Way Bill lookup completed",
            extra={
                "eway_bill_number": request.eway_bill_number,
                "booking_id": str(request.booking_id),
                "status": status,
            },
        )
        return response

    async def _read_cache(self, key: str) -> EWayBillFetchResponse | None:
        try:
            value = await self._cache.get(key)
            if value is None:
                return None
            return EWayBillFetchResponse.model_validate_json(value)
        except Exception:
            logger.warning("Ignoring unreadable E-Way Bill cache entry", exc_info=True)
            try:
                await self._cache.delete(key)
            except Exception:
                logger.debug("Failed to evict invalid cache entry", exc_info=True)
            return None

    async def _write_cache(
        self, key: str, response: EWayBillFetchResponse
    ) -> None:
        try:
            await self._cache.set(
                key,
                response.model_dump_json(),
                ex=CACHE_TTL_SECONDS,
            )
        except Exception:
            # Cache availability must not turn a successful persisted lookup into 5xx.
            logger.warning("Unable to cache E-Way Bill response", exc_info=True)

    @staticmethod
    def _parse_validity(raw_response: dict[str, Any]) -> datetime:
        raw_validity = raw_response.get("validUpto")
        if not isinstance(raw_validity, str):
            raise InvalidGSTResponseError("GST response is missing validUpto")
        try:
            parsed = datetime.fromisoformat(raw_validity.replace("Z", "+00:00"))
        except ValueError as exc:
            raise InvalidGSTResponseError(
                "GST response contains an invalid validUpto"
            ) from exc
        return EWayBillService._utc(parsed)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        """Normalize an aware value to UTC; GST's timezone-less values mean UTC."""
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _extract_commodity(raw_response: dict[str, Any]) -> str:
        value = next(
            (
                raw_response[key]
                for key in ("commodityCategory", "commodity_category", "category")
                if key in raw_response
            ),
            raw_response.get("prodDesc", ""),
        )
        normalized = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
        return normalized.strip("_")
