from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class ReviewOrigin(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "review_origins"
    __table_args__ = (
        UniqueConstraint("provider_name", "provider_review_id", name="uq_review_origin_provider_id"),
    )

    review_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    provider_review_id: Mapped[str | None] = mapped_column(String(500), index=True)
    provider_place_id: Mapped[str | None] = mapped_column(String(500), index=True)
    source_label: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(Text)
    contributor_id: Mapped[str | None] = mapped_column(String(500), index=True)
    author_profile_url: Mapped[str | None] = mapped_column(Text)
    author_avatar_url: Mapped[str | None] = mapped_column(Text)
    local_guide: Mapped[bool | None] = mapped_column()
    provider_review_count: Mapped[int | None] = mapped_column()
    provider_photo_count: Mapped[int | None] = mapped_column()
    provider_publication_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_edit_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_details: Mapped[dict | None] = mapped_column(JSONB)
    provider_translated_details: Mapped[dict | None] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    review = relationship("Review", back_populates="origins")
    images = relationship("ReviewImage", back_populates="origin", cascade="all, delete-orphan")
