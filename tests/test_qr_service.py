"""Comprehensive pytest tests for QR service module."""

from __future__ import annotations

import asyncio
import json
import os

import pytest

from modules.bookings.services.qr_service import (
    QRService,
    MissingQRSecretError,
    QRSignatureError,
    QRGenerationError,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def qr_secret() -> str:
    """Test HMAC secret (minimum 32 bytes)."""
    return "test-secret-key-with-minimum-32bytes!"


@pytest.fixture
def qr_service(qr_secret: str) -> QRService:
    """Instantiate QR service with test secret."""
    return QRService(gate_qr_secret=qr_secret)


# ============================================================================
# TEST: GATE KEY GENERATION
# ============================================================================


class TestGateKeyGeneration:
    """Test gate key generation."""

    def test_generate_gate_key_returns_string(self, qr_service: QRService) -> None:
        """Gate key is a string."""
        # Access the method indirectly through payload generation
        payload = {
            "booking_id": "RR001",
            "vehicle_reg": "HR38AB1",
            "departure_iso": "2026-07-10T15:00:00+05:30",
            "gate_key": qr_service._generate_gate_key(),
        }
        assert isinstance(payload["gate_key"], str)

    def test_generate_gate_key_length_64(self, qr_service: QRService) -> None:
        """Gate key is exactly 64 characters (32 bytes as hex)."""
        gate_key = qr_service._generate_gate_key()
        assert len(gate_key) == 64

    def test_generate_gate_key_is_hex(self, qr_service: QRService) -> None:
        """Gate key is valid hexadecimal."""
        gate_key = qr_service._generate_gate_key()
        # Should not raise ValueError
        int(gate_key, 16)

    def test_generate_gate_key_uniqueness(self, qr_service: QRService) -> None:
        """Two generated keys are different."""
        key1 = qr_service._generate_gate_key()
        key2 = qr_service._generate_gate_key()
        assert key1 != key2


# ============================================================================
# TEST: PAYLOAD BUILDING
# ============================================================================


class TestPayloadBuilding:
    """Test QR payload building."""

    def test_build_payload_contains_booking_id(self, qr_service: QRService) -> None:
        """Payload contains booking_id."""
        payload = qr_service._build_payload(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        assert "booking_id" in payload
        assert payload["booking_id"] == "RR001234"

    def test_build_payload_contains_vehicle_reg(self, qr_service: QRService) -> None:
        """Payload contains vehicle_reg."""
        payload = qr_service._build_payload(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        assert "vehicle_reg" in payload
        assert payload["vehicle_reg"] == "HR38AB1234"

    def test_build_payload_contains_departure_iso(
        self, qr_service: QRService
    ) -> None:
        """Payload contains departure_iso."""
        payload = qr_service._build_payload(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        assert "departure_iso" in payload
        assert payload["departure_iso"] == "2026-07-10T15:00:00+05:30"

    def test_build_payload_contains_gate_key(self, qr_service: QRService) -> None:
        """Payload contains generated gate_key."""
        payload = qr_service._build_payload(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        assert "gate_key" in payload
        assert len(payload["gate_key"]) == 64

    def test_build_payload_all_fields_present(self, qr_service: QRService) -> None:
        """Payload contains all required fields."""
        payload = qr_service._build_payload(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        required_fields = {"booking_id", "vehicle_reg", "departure_iso", "gate_key"}
        assert required_fields.issubset(payload.keys())


# ============================================================================
# TEST: PAYLOAD SIGNING
# ============================================================================


class TestPayloadSigning:
    """Test HMAC-SHA256 signing."""

    def test_sign_payload_returns_string(self, qr_service: QRService) -> None:
        """Signature is a string."""
        payload = {
            "booking_id": "RR001234",
            "vehicle_reg": "HR38AB1234",
            "departure_iso": "2026-07-10T15:00:00+05:30",
            "gate_key": "abc123def456",
        }
        signature = qr_service._sign_payload(payload)
        assert isinstance(signature, str)

    def test_sign_payload_non_empty(self, qr_service: QRService) -> None:
        """Signature is not empty."""
        payload = {
            "booking_id": "RR001234",
            "vehicle_reg": "HR38AB1234",
            "departure_iso": "2026-07-10T15:00:00+05:30",
            "gate_key": "abc123def456",
        }
        signature = qr_service._sign_payload(payload)
        assert len(signature) > 0

    def test_sign_payload_is_hex(self, qr_service: QRService) -> None:
        """Signature is valid hexadecimal."""
        payload = {
            "booking_id": "RR001234",
            "vehicle_reg": "HR38AB1234",
            "departure_iso": "2026-07-10T15:00:00+05:30",
            "gate_key": "abc123def456",
        }
        signature = qr_service._sign_payload(payload)
        # Should not raise ValueError
        int(signature, 16)

    def test_sign_payload_deterministic(self, qr_service: QRService) -> None:
        """Same payload generates same signature."""
        payload = {
            "booking_id": "RR001234",
            "vehicle_reg": "HR38AB1234",
            "departure_iso": "2026-07-10T15:00:00+05:30",
            "gate_key": "abc123def456",
        }
        sig1 = qr_service._sign_payload(payload)
        sig2 = qr_service._sign_payload(payload)
        assert sig1 == sig2

    def test_sign_payload_sha256_length(self, qr_service: QRService) -> None:
        """Signature is 64 characters (SHA256 in hex)."""
        payload = {
            "booking_id": "RR001234",
            "vehicle_reg": "HR38AB1234",
            "departure_iso": "2026-07-10T15:00:00+05:30",
            "gate_key": "abc123def456",
        }
        signature = qr_service._sign_payload(payload)
        assert len(signature) == 64


# ============================================================================
# TEST: SIGNATURE VERIFICATION - SUCCESS
# ============================================================================


class TestSignatureVerificationSuccess:
    """Test successful signature verification."""

    @pytest.mark.asyncio
    async def test_verify_signature_success(self, qr_service: QRService) -> None:
        """Validate QR with correct signature succeeds."""
        # Build payload
        payload = qr_service._build_payload(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )

        # Sign payload
        signature = qr_service._sign_payload(payload)

        # Create signed envelope
        signed_envelope = {
            "payload": payload,
            "signature": signature,
        }
        signed_json = json.dumps(signed_envelope)

        # Validate
        validated_payload = await qr_service.validate_qr(signed_json)

        # Verify payload is returned
        assert validated_payload == payload
        assert validated_payload["booking_id"] == "RR001234"

    @pytest.mark.asyncio
    async def test_verify_signature_returns_payload(
        self, qr_service: QRService
    ) -> None:
        """Validate QR returns original payload."""
        payload = qr_service._build_payload(
            booking_id="RR005678",
            vehicle_reg="HR38AB5678",
            departure_iso="2026-07-15T10:30:00+05:30",
        )
        signature = qr_service._sign_payload(payload)

        signed_json = json.dumps({"payload": payload, "signature": signature})
        validated = await qr_service.validate_qr(signed_json)

        assert validated["booking_id"] == "RR005678"
        assert validated["vehicle_reg"] == "HR38AB5678"


# ============================================================================
# TEST: SIGNATURE VERIFICATION - FAILURE
# ============================================================================


class TestSignatureVerificationFailure:
    """Test signature verification failures."""

    @pytest.mark.asyncio
    async def test_verify_signature_invalid_signature(
        self, qr_service: QRService
    ) -> None:
        """Validate QR with invalid signature raises error."""
        payload = qr_service._build_payload(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )

        # Use wrong signature
        signed_json = json.dumps({
            "payload": payload,
            "signature": "0" * 64,
        })

        with pytest.raises(QRSignatureError):
            await qr_service.validate_qr(signed_json)

    @pytest.mark.asyncio
    async def test_verify_signature_tampered_payload(
        self, qr_service: QRService
    ) -> None:
        """Validate QR with tampered payload raises error."""
        payload = qr_service._build_payload(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        signature = qr_service._sign_payload(payload)

        # Tamper with payload
        tampered_payload = payload.copy()
        tampered_payload["booking_id"] = "RR999999"

        signed_json = json.dumps({
            "payload": tampered_payload,
            "signature": signature,
        })

        with pytest.raises(QRSignatureError):
            await qr_service.validate_qr(signed_json)

    @pytest.mark.asyncio
    async def test_verify_signature_invalid_json(
        self, qr_service: QRService
    ) -> None:
        """Validate QR with invalid JSON raises error."""
        with pytest.raises(QRSignatureError):
            await qr_service.validate_qr("not valid json")

    @pytest.mark.asyncio
    async def test_verify_signature_missing_payload_field(
        self, qr_service: QRService
    ) -> None:
        """Validate QR missing payload field raises error."""
        signed_json = json.dumps({"signature": "0" * 64})
        with pytest.raises(QRSignatureError):
            await qr_service.validate_qr(signed_json)

    @pytest.mark.asyncio
    async def test_verify_signature_missing_signature_field(
        self, qr_service: QRService
    ) -> None:
        """Validate QR missing signature field raises error."""
        signed_json = json.dumps({"payload": {"booking_id": "RR001"}})
        with pytest.raises(QRSignatureError):
            await qr_service.validate_qr(signed_json)


# ============================================================================
# TEST: FULL QR GENERATION
# ============================================================================


class TestQRGeneration:
    """Test complete QR generation."""

    @pytest.mark.asyncio
    async def test_generate_qr_returns_dict(self, qr_service: QRService) -> None:
        """Generate QR returns dictionary."""
        result = await qr_service.generate_qr(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_qr_contains_payload(self, qr_service: QRService) -> None:
        """Generate QR returns payload."""
        result = await qr_service.generate_qr(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        assert "payload" in result
        assert result["payload"]["booking_id"] == "RR001234"

    @pytest.mark.asyncio
    async def test_generate_qr_contains_signature(self, qr_service: QRService) -> None:
        """Generate QR returns signature."""
        result = await qr_service.generate_qr(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        assert "signature" in result
        assert len(result["signature"]) == 64

    @pytest.mark.asyncio
    async def test_generate_qr_contains_qr_image(self, qr_service: QRService) -> None:
        """Generate QR returns PNG image bytes."""
        result = await qr_service.generate_qr(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        assert "qr_image" in result
        assert isinstance(result["qr_image"], bytes)
        assert len(result["qr_image"]) > 0

    @pytest.mark.asyncio
    async def test_generate_qr_image_is_png(self, qr_service: QRService) -> None:
        """Generated QR image is PNG format."""
        result = await qr_service.generate_qr(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        # PNG magic number: 89 50 4E 47 0D 0A 1A 0A
        assert result["qr_image"][:8] == b"\x89PNG\r\n\x1a\n"

    @pytest.mark.asyncio
    async def test_generate_qr_contains_gate_key(self, qr_service: QRService) -> None:
        """Generate QR returns gate_key."""
        result = await qr_service.generate_qr(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        assert "gate_key" in result
        assert len(result["gate_key"]) == 64

    @pytest.mark.asyncio
    async def test_generate_qr_payload_content(self, qr_service: QRService) -> None:
        """Generate QR payload has correct content."""
        result = await qr_service.generate_qr(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        payload = result["payload"]
        assert payload["booking_id"] == "RR001234"
        assert payload["vehicle_reg"] == "HR38AB1234"
        assert payload["departure_iso"] == "2026-07-10T15:00:00+05:30"


# ============================================================================
# TEST: ERROR HANDLING
# ============================================================================


class TestErrorHandling:
    """Test error handling."""

    def test_missing_secret_raises_error(self) -> None:
        """Missing GATE_QR_SECRET raises MissingQRSecretError."""
        # Save original env var
        original = os.environ.get("GATE_QR_SECRET")
        try:
            # Remove env var
            os.environ.pop("GATE_QR_SECRET", None)
            with pytest.raises(MissingQRSecretError):
                QRService()
        finally:
            # Restore env var
            if original:
                os.environ["GATE_QR_SECRET"] = original

    def test_empty_secret_raises_error(self) -> None:
        """Empty GATE_QR_SECRET raises MissingQRSecretError."""
        original = os.environ.get("GATE_QR_SECRET")
        try:
            os.environ["GATE_QR_SECRET"] = ""
            with pytest.raises(MissingQRSecretError):
                QRService()
        finally:
            if original:
                os.environ["GATE_QR_SECRET"] = original

    def test_init_with_explicit_secret(self) -> None:
        """Service initializes with explicit secret."""
        service = QRService(gate_qr_secret="explicit-secret-32-bytes-minimum!")
        assert service._secret == b"explicit-secret-32-bytes-minimum!"


# ============================================================================
# TEST: INTEGRATION
# ============================================================================


class TestIntegration:
    """Test integration scenarios."""

    @pytest.mark.asyncio
    async def test_end_to_end_generate_and_validate(
        self, qr_service: QRService
    ) -> None:
        """End-to-end: generate QR and validate it."""
        # Generate
        result = await qr_service.generate_qr(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )

        # Validate
        signed_json = json.dumps({
            "payload": result["payload"],
            "signature": result["signature"],
        })
        validated = await qr_service.validate_qr(signed_json)

        # Verify
        assert validated["booking_id"] == "RR001234"
        assert validated["vehicle_reg"] == "HR38AB1234"

    @pytest.mark.asyncio
    async def test_multiple_qr_generations_unique(
        self, qr_service: QRService
    ) -> None:
        """Multiple QR generations produce unique gate keys."""
        result1 = await qr_service.generate_qr(
            "RR001", "HR38AB1", "2026-07-10T15:00:00+05:30"
        )
        result2 = await qr_service.generate_qr(
            "RR002", "HR38AB2", "2026-07-10T15:00:00+05:30"
        )

        assert result1["gate_key"] != result2["gate_key"]
        assert result1["signature"] != result2["signature"]

    @pytest.mark.asyncio
    async def test_different_services_different_signatures(self) -> None:
        """Different services with different secrets produce different signatures."""
        service1 = QRService(gate_qr_secret="secret1-with-32-bytes-minimum!!!")
        service2 = QRService(gate_qr_secret="secret2-with-32-bytes-minimum!!!")

        result1 = await service1.generate_qr(
            "RR001", "HR38AB1", "2026-07-10T15:00:00+05:30"
        )
        result2 = await service2.generate_qr(
            "RR001", "HR38AB1", "2026-07-10T15:00:00+05:30"
        )

        # Same booking_id but different secrets should produce different signatures
        assert result1["signature"] != result2["signature"]
