"""Enforce one vehicle and one driver per booking.

Revision ID: 20260623_01
Revises: None
Create Date: 2026-06-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260623_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep the newest duplicate and enforce booking uniqueness."""
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY booking_id
                       ORDER BY created_at DESC, id DESC
                   ) AS row_number
            FROM vehicle_details
        )
        DELETE FROM vehicle_details AS target
        USING ranked
        WHERE target.id = ranked.id AND ranked.row_number > 1
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY booking_id
                       ORDER BY created_at DESC, id DESC
                   ) AS row_number
            FROM driver_details
        )
        DELETE FROM driver_details AS target
        USING ranked
        WHERE target.id = ranked.id AND ranked.row_number > 1
        """
    )
    op.create_unique_constraint(
        "uq_vehicle_details_booking_id", "vehicle_details", ["booking_id"]
    )
    op.create_unique_constraint(
        "uq_driver_details_booking_id", "driver_details", ["booking_id"]
    )


def downgrade() -> None:
    """Remove booking uniqueness while retaining the deduplicated data."""
    op.drop_constraint(
        "uq_driver_details_booking_id", "driver_details", type_="unique"
    )
    op.drop_constraint(
        "uq_vehicle_details_booking_id", "vehicle_details", type_="unique"
    )

