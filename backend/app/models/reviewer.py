from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Reviewer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reviewers"

    google_contributor_id: Mapped[str | None] = mapped_column(String(500), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(500))
    avatar_url: Mapped[str | None] = mapped_column(String)
    profile_url: Mapped[str | None] = mapped_column(String)
    local_guide: Mapped[bool | None] = mapped_column(Boolean)
    provider_review_count: Mapped[int | None] = mapped_column(Integer)
    provider_photo_count: Mapped[int | None] = mapped_column(Integer)
    profile_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contributor_profile: Mapped[dict | None] = mapped_column(JSONB)
    context_generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    context_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    context_status: Mapped[str] = mapped_column(String(20), default="not_loaded", nullable=False)
    provider_results_returned: Mapped[int | None] = mapped_column(Integer)
    accepted_food_and_drink_count: Mapped[int | None] = mapped_column(Integer)
    rejected_non_food_count: Mapped[int | None] = mapped_column(Integer)
    rejected_unknown_type_count: Mapped[int | None] = mapped_column(Integer)
    rejected_missing_required_data_count: Mapped[int | None] = mapped_column(Integer)

    reviews = relationship("Review", back_populates="reviewer")
    operations = relationship("ProviderOperation", back_populates="reviewer")
