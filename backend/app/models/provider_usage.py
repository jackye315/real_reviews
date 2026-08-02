from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin, utcnow


class ProviderUsage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "provider_usage"
    __table_args__ = (UniqueConstraint("provider", "plan_period", "operation_type", name="uq_provider_usage_period_operation"),)

    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    plan_period: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(String(50), default="serpapi_reviews", nullable=False, index=True)
    successful_request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_response_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
