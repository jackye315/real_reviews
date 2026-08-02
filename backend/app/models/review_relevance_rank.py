from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReviewRelevanceRank(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_relevance_ranks"
    __table_args__ = (
        UniqueConstraint("place_id", "provider", "language_code", "snapshot_id", "review_id", name="uq_relevance_membership"),
        UniqueConstraint("place_id", "provider", "language_code", "snapshot_id", "rank", name="uq_relevance_rank"),
    )

    place_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), nullable=False, index=True)
    review_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_sort: Mapped[str] = mapped_column(String(50), nullable=False, default="qualityScore")
    language_code: Mapped[str] = mapped_column(String(20), nullable=False, default="en")
    snapshot_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
