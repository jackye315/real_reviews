from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProviderBudgetPeriod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_budget_periods"
    __table_args__ = (UniqueConstraint("provider", "plan_period", name="uq_provider_budget_period"),)

    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    plan_period: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    configured_local_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_reported_remaining: Mapped[int | None] = mapped_column(Integer)
    provider_hourly_used: Mapped[int | None] = mapped_column(Integer)
    provider_hourly_limit: Mapped[int | None] = mapped_column(Integer)
    plan_renewal_date: Mapped[date | None] = mapped_column(Date)
    snapshot_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
