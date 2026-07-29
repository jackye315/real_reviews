"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-28 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "places",
        sa.Column("google_place_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=500), nullable=False),
        sa.Column("formatted_address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("viewport", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("place_types", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("google_maps_url", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_places_google_place_id"), "places", ["google_place_id"], unique=True)

    op.create_table(
        "provider_usage",
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("plan_period", sa.String(length=20), nullable=False),
        sa.Column("successful_request_count", sa.Integer(), nullable=False),
        sa.Column("cached_response_count", sa.Integer(), nullable=False),
        sa.Column("failed_request_count", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "plan_period", name="uq_provider_usage_period"),
    )
    op.create_index(op.f("ix_provider_usage_provider"), "provider_usage", ["provider"], unique=False)
    op.create_index(op.f("ix_provider_usage_plan_period"), "provider_usage", ["plan_period"], unique=False)

    op.create_table(
        "reviews",
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_display_name", sa.String(length=500), nullable=True),
        sa.Column("author_avatar_url", sa.Text(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=True),
        sa.Column("publication_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edit_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canonical_source_url", sa.Text(), nullable=True),
        sa.Column("normalized_content_hash", sa.String(length=64), nullable=False),
        sa.Column("first_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("suspected_duplicate", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("place_id", "normalized_content_hash", "rating", name="uq_review_content"),
    )
    op.create_index("ix_reviews_place_publication", "reviews", ["place_id", "publication_timestamp"], unique=False)
    op.create_index(op.f("ix_reviews_normalized_content_hash"), "reviews", ["normalized_content_hash"], unique=False)
    op.create_index(op.f("ix_reviews_place_id"), "reviews", ["place_id"], unique=False)

    op.create_table(
        "review_sync_runs",
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("requested_target_count", sa.Integer(), nullable=False),
        sa.Column("collected_unique_count", sa.Integer(), nullable=False),
        sa.Column("successful_request_count", sa.Integer(), nullable=False),
        sa.Column("pagination_cursor", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_review_sync_runs_place_id"), "review_sync_runs", ["place_id"], unique=False)
    op.create_index(op.f("ix_review_sync_runs_status"), "review_sync_runs", ["status"], unique=False)

    op.create_table(
        "review_origins",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_name", sa.String(length=100), nullable=False),
        sa.Column("provider_review_id", sa.String(length=500), nullable=True),
        sa.Column("provider_place_id", sa.String(length=500), nullable=True),
        sa.Column("source_label", sa.String(length=200), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("contributor_id", sa.String(length=500), nullable=True),
        sa.Column("author_profile_url", sa.Text(), nullable=True),
        sa.Column("author_avatar_url", sa.Text(), nullable=True),
        sa.Column("provider_publication_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_edit_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_name", "provider_review_id", name="uq_review_origin_provider_id"),
    )
    op.create_index(op.f("ix_review_origins_contributor_id"), "review_origins", ["contributor_id"], unique=False)
    op.create_index(op.f("ix_review_origins_provider_name"), "review_origins", ["provider_name"], unique=False)
    op.create_index(op.f("ix_review_origins_provider_place_id"), "review_origins", ["provider_place_id"], unique=False)
    op.create_index(op.f("ix_review_origins_provider_review_id"), "review_origins", ["provider_review_id"], unique=False)
    op.create_index(op.f("ix_review_origins_review_id"), "review_origins", ["review_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_review_origins_review_id"), table_name="review_origins")
    op.drop_index(op.f("ix_review_origins_provider_review_id"), table_name="review_origins")
    op.drop_index(op.f("ix_review_origins_provider_place_id"), table_name="review_origins")
    op.drop_index(op.f("ix_review_origins_provider_name"), table_name="review_origins")
    op.drop_index(op.f("ix_review_origins_contributor_id"), table_name="review_origins")
    op.drop_table("review_origins")
    op.drop_index(op.f("ix_review_sync_runs_status"), table_name="review_sync_runs")
    op.drop_index(op.f("ix_review_sync_runs_place_id"), table_name="review_sync_runs")
    op.drop_table("review_sync_runs")
    op.drop_index(op.f("ix_reviews_place_id"), table_name="reviews")
    op.drop_index(op.f("ix_reviews_normalized_content_hash"), table_name="reviews")
    op.drop_index("ix_reviews_place_publication", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index(op.f("ix_provider_usage_plan_period"), table_name="provider_usage")
    op.drop_index(op.f("ix_provider_usage_provider"), table_name="provider_usage")
    op.drop_table("provider_usage")
    op.drop_index(op.f("ix_places_google_place_id"), table_name="places")
    op.drop_table("places")
