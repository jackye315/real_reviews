"""add review topics

Revision ID: 0004_add_review_topics
Revises: 0003_add_sync_stop_reason
Create Date: 2026-07-29 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_add_review_topics"
down_revision: str | None = "0003_add_sync_stop_reason"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_topics",
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("provider_topic_id", sa.Text(), nullable=False),
        sa.Column("keyword", sa.Text(), nullable=False),
        sa.Column("mentions", sa.Integer(), nullable=True),
        sa.Column("language_code", sa.String(length=20), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "place_id",
            "provider_name",
            "provider_topic_id",
            "language_code",
            name="uq_review_topics_place_provider_topic_language",
        ),
    )
    op.create_index(
        "ix_review_topics_place_provider_active_rank",
        "review_topics",
        ["place_id", "provider_name", "active", "rank"],
        unique=False,
    )
    op.add_column("review_sync_runs", sa.Column("topic_field_observed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("review_sync_runs", sa.Column("topic_count_observed", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("review_sync_runs", "topic_field_observed", server_default=None)
    op.alter_column("review_sync_runs", "topic_count_observed", server_default=None)


def downgrade() -> None:
    op.drop_column("review_sync_runs", "topic_count_observed")
    op.drop_column("review_sync_runs", "topic_field_observed")
    op.drop_index("ix_review_topics_place_provider_active_rank", table_name="review_topics")
    op.drop_table("review_topics")
