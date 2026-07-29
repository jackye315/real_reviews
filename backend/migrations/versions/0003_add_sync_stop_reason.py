"""add sync stop reason

Revision ID: 0003_add_sync_stop_reason
Revises: 0002_relax_review_uniqueness
Create Date: 2026-07-29 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_sync_stop_reason"
down_revision: str | None = "0002_relax_review_uniqueness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("review_sync_runs", sa.Column("stop_reason", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("review_sync_runs", "stop_reason")
