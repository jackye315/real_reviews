"""add relevance snapshots

Revision ID: 0009_relevance_snapshots
Revises: 0008_reviewer_context
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_relevance_snapshots"
down_revision: str | None = "0008_reviewer_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_review_collection_state_place_provider", "review_collection_states", type_="unique")
    op.add_column("review_collection_states", sa.Column("provider_sort", sa.String(length=50), nullable=False, server_default="newestFirst"))
    op.add_column("review_collection_states", sa.Column("active_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("review_collection_states", sa.Column("pending_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("review_collection_states", sa.Column("ranked_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("review_collection_states", sa.Column("next_rank", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("review_collection_states", sa.Column("snapshot_status", sa.String(length=20), nullable=True))
    op.add_column("review_collection_states", sa.Column("relevance_fetched_at", sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint("uq_review_collection_state_place_provider_sort", "review_collection_states", ["place_id", "provider", "provider_sort"])
    op.create_table(
        "review_relevance_ranks",
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_sort", sa.String(length=50), nullable=False, server_default="qualityScore"),
        sa.Column("language_code", sa.String(length=20), nullable=False, server_default="en"),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("place_id", "provider", "language_code", "snapshot_id", "review_id", name="uq_relevance_membership"),
        sa.UniqueConstraint("place_id", "provider", "language_code", "snapshot_id", "rank", name="uq_relevance_rank"),
    )
    op.create_index("ix_review_relevance_ranks_place_id", "review_relevance_ranks", ["place_id"])
    op.create_index("ix_review_relevance_ranks_review_id", "review_relevance_ranks", ["review_id"])


def downgrade() -> None:
    op.drop_index("ix_review_relevance_ranks_review_id", table_name="review_relevance_ranks")
    op.drop_index("ix_review_relevance_ranks_place_id", table_name="review_relevance_ranks")
    op.drop_table("review_relevance_ranks")
    op.drop_constraint("uq_review_collection_state_place_provider_sort", "review_collection_states", type_="unique")
    for name in ("relevance_fetched_at", "snapshot_status", "next_rank", "ranked_count", "pending_snapshot_id", "active_snapshot_id", "provider_sort"):
        op.drop_column("review_collection_states", name)
    op.create_unique_constraint("uq_review_collection_state_place_provider", "review_collection_states", ["place_id", "provider"])
