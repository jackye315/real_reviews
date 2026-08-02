"""add rich review data

Revision ID: 0007_review_rich_data
Revises: 0006_review_pagination
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_review_rich_data"
down_revision: str | None = "0006_review_pagination"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reviews", sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("reviews", sa.Column("translated_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("reviews", sa.Column("rich_data_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("review_origins", sa.Column("provider_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("review_origins", sa.Column("provider_translated_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_table(
        "review_images",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("review_origin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("provider_image_url", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["review_origin_id"], ["review_origins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("review_origin_id", "provider_image_url", name="uq_review_image_origin_url"),
    )
    op.create_index(op.f("ix_review_images_review_id"), "review_images", ["review_id"], unique=False)
    op.create_index(op.f("ix_review_images_review_origin_id"), "review_images", ["review_origin_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_review_images_review_origin_id"), table_name="review_images")
    op.drop_index(op.f("ix_review_images_review_id"), table_name="review_images")
    op.drop_table("review_images")
    op.drop_column("review_origins", "provider_translated_details")
    op.drop_column("review_origins", "provider_details")
    op.drop_column("reviews", "rich_data_updated_at")
    op.drop_column("reviews", "translated_details")
    op.drop_column("reviews", "details")
