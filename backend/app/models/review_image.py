from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class ReviewImage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "review_images"
    __table_args__ = (
        UniqueConstraint("review_origin_id", "provider_image_url", name="uq_review_image_origin_url"),
    )

    review_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    review_origin_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("review_origins.id", ondelete="CASCADE"), index=True)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_image_url: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    review = relationship("Review", back_populates="images")
    origin = relationship("ReviewOrigin", back_populates="images")
