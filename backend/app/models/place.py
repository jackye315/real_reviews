from __future__ import annotations

from typing import Any

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Place(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "places"

    google_place_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    formatted_address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    viewport: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    place_types: Mapped[list[str] | None] = mapped_column(JSONB)
    google_maps_url: Mapped[str | None] = mapped_column(Text)
    llm_dish_summary: Mapped[str | None] = mapped_column(Text)
    review_corpus_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="selected", nullable=False)
    provider_type: Mapped[str | None] = mapped_column(String(200))
    normalized_venue_type: Mapped[str | None] = mapped_column(String(100), index=True)
    comparison_family: Mapped[str | None] = mapped_column(String(100), index=True)
    type_source: Mapped[str | None] = mapped_column(String(100))
    type_confidence: Mapped[str | None] = mapped_column(String(50))
    classifier_version: Mapped[str | None] = mapped_column(String(50))

    reviews = relationship("Review", back_populates="place", cascade="all, delete-orphan")
    topics = relationship("ReviewTopic", back_populates="place", cascade="all, delete-orphan")
    sync_runs = relationship("ReviewSyncRun", back_populates="place", cascade="all, delete-orphan")
    collection_states = relationship("ReviewCollectionState", back_populates="place", cascade="all, delete-orphan")
    data_ids = relationship("PlaceDataId", back_populates="place", cascade="all, delete-orphan")
