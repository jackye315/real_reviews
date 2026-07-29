from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.provider_usage import ProviderUsage


def current_plan_period() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


class UsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self) -> list[ProviderUsage]:
        result = await self.session.execute(select(ProviderUsage).order_by(ProviderUsage.provider))
        return list(result.scalars())

    async def get_or_create(self, provider: str, plan_period: str | None = None) -> ProviderUsage:
        period = plan_period or current_plan_period()
        result = await self.session.execute(
            select(ProviderUsage).where(
                ProviderUsage.provider == provider, ProviderUsage.plan_period == period
            )
        )
        usage = result.scalar_one_or_none()
        if usage is None:
            usage = ProviderUsage(provider=provider, plan_period=period)
            self.session.add(usage)
            await self.session.flush()
        return usage

    async def remaining_success_budget(self, provider: str, budget: int) -> int:
        usage = await self.get_or_create(provider)
        return max(0, budget - usage.successful_request_count)

    async def increment(self, provider: str, successful: int = 0, cached: int = 0, failed: int = 0) -> ProviderUsage:
        usage = await self.get_or_create(provider)
        usage.successful_request_count += successful
        usage.cached_response_count += cached
        usage.failed_request_count += failed
        await self.session.flush()
        return usage
