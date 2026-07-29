"""relax review uniqueness

Revision ID: 0002_relax_review_uniqueness
Revises: 0001_initial
Create Date: 2026-07-29 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_relax_review_uniqueness"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_review_content", "reviews", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_review_content",
        "reviews",
        ["place_id", "normalized_content_hash", "rating"],
    )
