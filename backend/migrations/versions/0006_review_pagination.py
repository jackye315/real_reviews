"""add review pagination state

Revision ID: 0006_review_pagination
Revises: 0005_provider_budget_ops
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_review_pagination"
down_revision: str | None = "0005_provider_budget_ops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("places", sa.Column("review_corpus_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "review_collection_states",
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("pagination_cursor", sa.Text(), nullable=True),
        sa.Column("cursor_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exhausted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("place_id", "provider", name="uq_review_collection_state_place_provider"),
    )
    op.add_column("provider_budget_reservations", sa.Column("result_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("provider_budget_reservations", "result_metadata")
    op.drop_table("review_collection_states")
    op.drop_column("places", "review_corpus_version")
