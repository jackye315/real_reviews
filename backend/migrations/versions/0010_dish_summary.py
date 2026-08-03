"""add saved local dish summary

Revision ID: 0010_dish_summary
Revises: 0009_relevance_snapshots
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_dish_summary"
down_revision: str | None = "0009_relevance_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("places", sa.Column("llm_dish_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("places", "llm_dish_summary")
