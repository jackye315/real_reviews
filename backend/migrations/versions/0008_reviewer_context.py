"""add reviewer context

Revision ID: 0008_reviewer_context
Revises: 0007_review_rich_data
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_reviewer_context"
down_revision: str | None = "0007_review_rich_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "reviewers",
        sa.Column("google_contributor_id", sa.String(length=500), nullable=True),
        sa.Column("display_name", sa.String(length=500), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("profile_url", sa.Text(), nullable=True),
        sa.Column("local_guide", sa.Boolean(), nullable=True),
        sa.Column("provider_review_count", sa.Integer(), nullable=True),
        sa.Column("provider_photo_count", sa.Integer(), nullable=True),
        sa.Column("profile_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contributor_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("context_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context_status", sa.String(length=20), nullable=False, server_default="not_loaded"),
        sa.Column("provider_results_returned", sa.Integer(), nullable=True),
        sa.Column("accepted_food_and_drink_count", sa.Integer(), nullable=True),
        sa.Column("rejected_non_food_count", sa.Integer(), nullable=True),
        sa.Column("rejected_unknown_type_count", sa.Integer(), nullable=True),
        sa.Column("rejected_missing_required_data_count", sa.Integer(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_contributor_id", name="uq_reviewers_google_contributor_id"),
    )
    op.create_index("ix_reviewers_google_contributor_id", "reviewers", ["google_contributor_id"])

    op.alter_column("places", "google_place_id", existing_type=sa.String(length=255), nullable=True)
    op.add_column("places", sa.Column("state", sa.String(length=20), nullable=False, server_default="selected"))
    for column, length in (("provider_type", 200), ("normalized_venue_type", 100), ("comparison_family", 100), ("type_source", 100), ("type_confidence", 50), ("classifier_version", 50)):
        op.add_column("places", sa.Column(column, sa.String(length=length), nullable=True))
    op.create_index("ix_places_normalized_venue_type", "places", ["normalized_venue_type"])
    op.create_index("ix_places_comparison_family", "places", ["comparison_family"])
    op.create_table(
        "place_data_ids",
        sa.Column("data_id", sa.String(length=500), nullable=False),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("data_id"),
    )
    op.create_index("ix_place_data_ids_place_id", "place_data_ids", ["place_id"])

    op.add_column("review_origins", sa.Column("local_guide", sa.Boolean(), nullable=True))
    op.add_column("review_origins", sa.Column("provider_review_count", sa.Integer(), nullable=True))
    op.add_column("review_origins", sa.Column("provider_photo_count", sa.Integer(), nullable=True))
    op.add_column("reviews", sa.Column("google_review_id", sa.String(length=500), nullable=True))
    op.add_column("reviews", sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("reviews", sa.Column("observed_data_id", sa.String(length=500), nullable=True))
    for column in ("seen_via_restaurant_at", "seen_via_contributor_at", "publication_date_lower_bound", "publication_date_upper_bound"):
        op.add_column("reviews", sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.add_column("reviews", sa.Column("contributor_generation", sa.Integer(), nullable=True))
    op.add_column("reviews", sa.Column("provider_date_text", sa.Text(), nullable=True))
    op.add_column("reviews", sa.Column("publication_date_precision", sa.String(length=20), nullable=True))
    op.add_column("reviews", sa.Column("publication_date_is_approximate", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("reviews", sa.Column("publication_date_basis", sa.String(length=30), nullable=True))
    op.create_foreign_key("fk_reviews_reviewer_id", "reviews", "reviewers", ["reviewer_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_reviews_observed_data_id", "reviews", ["observed_data_id"])
    op.create_index("ix_reviews_reviewer_generation_publication", "reviews", ["reviewer_id", "contributor_generation", "publication_timestamp"])

    op.execute("""
        INSERT INTO reviewers (id, google_contributor_id, display_name, avatar_url, profile_url, profile_observed_at, context_generation, context_status, created_at, updated_at)
        SELECT gen_random_uuid(), origin.contributor_id, max(review.author_display_name), max(origin.author_avatar_url), max(origin.author_profile_url), max(origin.fetched_at), 0, 'not_loaded', now(), now()
        FROM review_origins AS origin JOIN reviews AS review ON review.id = origin.review_id
        WHERE origin.contributor_id IS NOT NULL
        GROUP BY origin.contributor_id
        ON CONFLICT (google_contributor_id) DO NOTHING
    """)
    op.execute("""
        UPDATE reviews AS review SET reviewer_id = reviewer.id
        FROM review_origins AS origin JOIN reviewers AS reviewer ON reviewer.google_contributor_id = origin.contributor_id
        WHERE origin.review_id = review.id AND review.reviewer_id IS NULL
    """)
    op.execute("""
        WITH candidates AS (
          SELECT origin.review_id, origin.provider_review_id,
                 count(*) OVER (PARTITION BY origin.provider_review_id) AS matches,
                 row_number() OVER (PARTITION BY origin.review_id ORDER BY origin.fetched_at DESC) AS rank
          FROM review_origins AS origin
          WHERE origin.provider_review_id IS NOT NULL
        )
        UPDATE reviews AS review SET google_review_id = candidates.provider_review_id
        FROM candidates
        WHERE candidates.review_id = review.id AND candidates.rank = 1 AND candidates.matches = 1
    """)
    op.create_index("uq_reviews_google_review_id_not_null", "reviews", ["google_review_id"], unique=True, postgresql_where=sa.text("google_review_id IS NOT NULL"))

    op.add_column("provider_budget_reservations", sa.Column("reviewer_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_provider_operations_reviewer_id", "provider_budget_reservations", "reviewers", ["reviewer_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_provider_budget_reservations_reviewer_id", "provider_budget_reservations", ["reviewer_id"])

    op.add_column("provider_usage", sa.Column("operation_type", sa.String(length=50), nullable=False, server_default="serpapi_reviews"))
    op.drop_constraint("uq_provider_usage_period", "provider_usage", type_="unique")
    op.create_unique_constraint("uq_provider_usage_period_operation", "provider_usage", ["provider", "plan_period", "operation_type"])
    op.create_index("ix_provider_usage_operation_type", "provider_usage", ["operation_type"])


def downgrade() -> None:
    op.drop_index("ix_provider_usage_operation_type", table_name="provider_usage")
    op.drop_constraint("uq_provider_usage_period_operation", "provider_usage", type_="unique")
    op.create_unique_constraint("uq_provider_usage_period", "provider_usage", ["provider", "plan_period"])
    op.drop_column("provider_usage", "operation_type")
    op.drop_index("ix_provider_budget_reservations_reviewer_id", table_name="provider_budget_reservations")
    op.drop_constraint("fk_provider_operations_reviewer_id", "provider_budget_reservations", type_="foreignkey")
    op.drop_column("provider_budget_reservations", "reviewer_id")
    op.drop_index("uq_reviews_google_review_id_not_null", table_name="reviews")
    op.drop_index("ix_reviews_reviewer_generation_publication", table_name="reviews")
    op.drop_index("ix_reviews_observed_data_id", table_name="reviews")
    op.drop_constraint("fk_reviews_reviewer_id", "reviews", type_="foreignkey")
    for column in ("publication_date_basis", "publication_date_is_approximate", "publication_date_precision", "provider_date_text", "contributor_generation", "publication_date_upper_bound", "publication_date_lower_bound", "seen_via_contributor_at", "seen_via_restaurant_at", "observed_data_id", "reviewer_id", "google_review_id"):
        op.drop_column("reviews", column)
    for column in ("provider_photo_count", "provider_review_count", "local_guide"):
        op.drop_column("review_origins", column)
    op.drop_index("ix_place_data_ids_place_id", table_name="place_data_ids")
    op.drop_table("place_data_ids")
    op.drop_index("ix_places_comparison_family", table_name="places")
    op.drop_index("ix_places_normalized_venue_type", table_name="places")
    for column in ("classifier_version", "type_confidence", "type_source", "comparison_family", "normalized_venue_type", "provider_type", "state"):
        op.drop_column("places", column)
    op.alter_column("places", "google_place_id", existing_type=sa.String(length=255), nullable=False)
    op.drop_index("ix_reviewers_google_contributor_id", table_name="reviewers")
    op.drop_table("reviewers")
