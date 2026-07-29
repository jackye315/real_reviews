from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class ReviewSyncRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "review_sync_runs"

    place_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    collected_unique_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    topic_field_observed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    topic_count_observed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pagination_cursor: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False, index=True)
    stop_reason: Mapped[str | None] = mapped_column(String(100))
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    place = relationship("Place", back_populates="sync_runs")
