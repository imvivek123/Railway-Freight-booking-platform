"""Business thresholds and response messages for vehicle eligibility."""

from typing import Final

MAX_HEIGHT_M: Final[float] = 3.8
MAX_LENGTH_M: Final[float] = 16.5
MAX_WIDTH_M: Final[float] = 2.6
MAX_GVW_TONNES: Final[float] = 40.0

HEIGHT_REVIEW_MIN_M: Final[float] = 3.5
GVW_REVIEW_MIN_TONNES: Final[float] = 35.0

HEIGHT_WARNING: Final[str] = "Vehicle height exceeds preferred limit"
WEIGHT_WARNING: Final[str] = "Vehicle weight requires manual review"

HEIGHT_REJECTION: Final[str] = "Vehicle height exceeds maximum limit"
LENGTH_REJECTION: Final[str] = "Vehicle length exceeds maximum limit"
WIDTH_REJECTION: Final[str] = "Vehicle width exceeds maximum limit"
WEIGHT_REJECTION: Final[str] = "Vehicle weight exceeds maximum limit"

ELIGIBLE: Final[str] = "ELIGIBLE"
CONDITIONAL: Final[str] = "CONDITIONAL"
REJECTED: Final[str] = "REJECTED"
DRIVER_VALID: Final[str] = "VALID"

