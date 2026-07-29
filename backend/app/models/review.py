from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class Review(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (Index("ix_reviews_place_publication", "place_id", "publication_timestamp"),)

    place_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), index=True)
    author_display_name: Mapped[str | None] = mapped_column(String(500))
    author_avatar_url: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    original_text: Mapped[str | None] = mapped_column(Text)
    publication_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_edit_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canonical_source_url: Mapped[str | None] = mapped_column(Text)
    normalized_content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    first_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    suspected_duplicate: Mapped[bool] = mapped_column(default=False, nullable=False)

    place = relationship("Place", back_populates="reviews")
    origins = relationship("ReviewOrigin", back_populates="review", cascade="all, delete-orphan")
