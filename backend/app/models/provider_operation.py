from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderOperation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_budget_reservations"
    __table_args__ = (
        UniqueConstraint("provider", "plan_period", "idempotency_key", name="uq_provider_operation_idempotency"),
    )

    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    plan_period: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    place_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("places.id", ondelete="SET NULL"), index=True)
    reviewer_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("reviewers.id", ondelete="SET NULL"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_units: Mapped[int] = mapped_column(Integer, nullable=False)
    successful_request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_response_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    uncertain_request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    released_reserved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    collected_unique_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="reserved", nullable=False, index=True)
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stop_reason: Mapped[str | None] = mapped_column(String(100))
    error_summary: Mapped[str | None] = mapped_column(Text)
    result_metadata: Mapped[dict | None] = mapped_column(JSONB)

    place = relationship("Place", lazy="selectin")
    reviewer = relationship("Reviewer", back_populates="operations", lazy="selectin")
