from __future__ import annotations

from typing import Any

from sqlalchemy import Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Place(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "places"

    google_place_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    formatted_address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    viewport: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    place_types: Mapped[list[str] | None] = mapped_column(JSONB)
    google_maps_url: Mapped[str | None] = mapped_column(Text)

    reviews = relationship("Review", back_populates="place", cascade="all, delete-orphan")
    topics = relationship("ReviewTopic", back_populates="place", cascade="all, delete-orphan")
    sync_runs = relationship("ReviewSyncRun", back_populates="place", cascade="all, delete-orphan")
