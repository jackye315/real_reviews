from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReviewCollectionState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_collection_states"
    __table_args__ = (UniqueConstraint("place_id", "provider", "provider_sort", name="uq_review_collection_state_place_provider_sort"),)

    place_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("places.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_sort: Mapped[str] = mapped_column(String(50), nullable=False, default="newestFirst")
    active_snapshot_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    pending_snapshot_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    ranked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot_status: Mapped[str | None] = mapped_column(String(20))
    relevance_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pagination_cursor: Mapped[str | None] = mapped_column(Text)
    cursor_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exhausted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    place = relationship("Place", back_populates="collection_states")
