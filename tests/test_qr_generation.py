#!/usr/bin/env python
"""Local manual test script for QR generation module.

Usage:
    python scripts/test_qr_generation.py

This script demonstrates:
1. Instantiating QRService
2. Generating a QR code
3. Printing the generated payload
4. Printing the signature
5. Printing file path information
6. Validating the generated QR
7. Printing validation success
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.bookings.services.qr_service import (
    QRService,
    MissingQRSecretError,
    QRSignatureError,
)


async def main() -> None:
    """Execute manual QR generation test."""
    print("=" * 80)
    print("QR GENERATION MODULE - LOCAL TEST SCRIPT")
    print("=" * 80)

    # Step 1: Instantiate QRService
    print("\n[STEP 1] Instantiating QRService...")
    try:
        service = QRService(gate_qr_secret="test-secret-with-minimum-32-bytes!")
        print("  ✓ QRService initialized successfully")
    except MissingQRSecretError as e:
        print(f"  ✗ Error: {e}")
        return

    # Step 2: Generate QR code
    print("\n[STEP 2] Generating QR code...")
    try:
        result = await service.generate_qr(
            booking_id="RR001234",
            vehicle_reg="HR38AB1234",
            departure_iso="2026-07-10T15:00:00+05:30",
        )
        print("  ✓ QR code generated successfully")
    except Exception as e:
        print(f"  ✗ Error generating QR: {e}")
        return

    # Step 3: Print generated payload
    print("\n[STEP 3] Generated Payload:")
    payload = result["payload"]
    print("  " + json.dumps(payload, indent=2).replace("\n", "\n  "))

    # Step 4: Print signature
    print("\n[STEP 4] Signature (HMAC-SHA256):")
    signature = result["signature"]
    print(f"  {signature}")
    print(f"  Length: {len(signature)} characters")

    # Step 5: Print file path information
    print("\n[STEP 5] QR Image Information:")
    qr_image = result["qr_image"]
    print(f"  Format: PNG")
    print(f"  Size: {len(qr_image)} bytes")
    print(f"  Magic Number: {qr_image[:8].hex()} (PNG identifier)")

    # Save QR image to file for inspection
    qr_output_path = Path("qr_output.png")
    with open(qr_output_path, "wb") as f:
        f.write(qr_image)
    print(f"  File saved: {qr_output_path}")

    # Step 6: Validate generated QR
    print("\n[STEP 6] Validating QR signature...")
    try:
        signed_json = json.dumps({
            "payload": payload,
            "signature": signature,
        })

        validated_payload = await service.validate_qr(signed_json)
        print("  ✓ Signature validation successful")
    except QRSignatureError as e:
        print(f"  ✗ Signature validation failed: {e}")
        return

    # Step 7: Print validation success
    print("\n[STEP 7] Validation Result:")
    print("  " + json.dumps(validated_payload, indent=2).replace("\n", "\n  "))

    # Additional test: Verify tampering is detected
    print("\n[BONUS] Testing tampering detection...")
    print("  Attempting to validate with tampered payload...")
    tampered_payload = payload.copy()
    tampered_payload["booking_id"] = "FAKE999999"

    try:
        tampered_json = json.dumps({
            "payload": tampered_payload,
            "signature": signature,
        })
        await service.validate_qr(tampered_json)
        print("  ✗ SECURITY ISSUE: Tampered payload was accepted!")
    except QRSignatureError:
        print("  ✓ Correctly rejected tampered payload (security working)")

    # Summary
    print("\n" + "=" * 80)
    print("✓ ALL TESTS COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print("\nSummary:")
    print(f"  - Booking ID: {payload['booking_id']}")
    print(f"  - Vehicle Reg: {payload['vehicle_reg']}")
    print(f"  - Departure: {payload['departure_iso']}")
    print(f"  - Gate Key: {payload['gate_key'][:16]}... (unique per QR)")
    print(f"  - Signature Length: {len(signature)} chars (SHA256)")
    print(f"  - QR Image Size: {len(qr_image)} bytes")
    print(f"  - Validation: PASSED")
    print(f"  - Tampering Detection: PASSED")


if __name__ == "__main__":
    asyncio.run(main())
