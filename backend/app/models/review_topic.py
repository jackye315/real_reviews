from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class ReviewTopic(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "review_topics"
    __table_args__ = (
        UniqueConstraint(
            "place_id",
            "provider_name",
            "provider_topic_id",
            "language_code",
            name="uq_review_topics_place_provider_topic_language",
        ),
        Index("ix_review_topics_place_provider_active_rank", "place_id", "provider_name", "active", "rank"),
    )

    place_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_topic_id: Mapped[str] = mapped_column(Text, nullable=False)
    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    mentions: Mapped[int | None] = mapped_column(Integer)
    language_code: Mapped[str | None] = mapped_column(String(20))
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    snapshot_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    place = relationship("Place", back_populates="topics")
