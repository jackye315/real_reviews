"""add provider budget reservations

Revision ID: 0005_provider_budget_ops
Revises: 0004_add_review_topics
Create Date: 2026-07-30 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_provider_budget_ops"
down_revision: str | None = "0004_add_review_topics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_budget_periods",
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("plan_period", sa.String(length=64), nullable=False),
        sa.Column("configured_local_budget", sa.Integer(), nullable=False),
        sa.Column("provider_reported_remaining", sa.Integer(), nullable=True),
        sa.Column("provider_hourly_used", sa.Integer(), nullable=True),
        sa.Column("provider_hourly_limit", sa.Integer(), nullable=True),
        sa.Column("plan_renewal_date", sa.Date(), nullable=True),
        sa.Column("snapshot_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "plan_period", name="uq_provider_budget_period"),
    )
    op.create_index("ix_provider_budget_periods_provider", "provider_budget_periods", ["provider"])
    op.create_index("ix_provider_budget_periods_plan_period", "provider_budget_periods", ["plan_period"])

    op.create_table(
        "provider_budget_reservations",
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("plan_period", sa.String(length=64), nullable=False),
        sa.Column("operation_type", sa.String(length=50), nullable=False),
        sa.Column("place_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("requested_units", sa.Integer(), nullable=False),
        sa.Column("successful_request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_response_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uncertain_request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("released_reserved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("collected_unique_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="reserved"),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stop_reason", sa.String(length=100), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "plan_period", "idempotency_key", name="uq_provider_operation_idempotency"),
    )
    for column in ("provider", "plan_period", "operation_type", "place_id", "status", "lease_expires_at"):
        op.create_index(f"ix_provider_budget_reservations_{column}", "provider_budget_reservations", [column])


def downgrade() -> None:
    op.drop_table("provider_budget_reservations")
    op.drop_table("provider_budget_periods")
