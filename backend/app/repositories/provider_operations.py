from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.models.provider_budget_period import ProviderBudgetPeriod
from app.models.provider_operation import ProviderOperation
from app.models.reviewer import Reviewer
from app.providers.serpapi_account import SerpApiAccountSnapshot
from app.repositories.usage import current_plan_period

ACTIVE_STATUSES = ("reserved", "running")
TERMINAL_STATUSES = ("completed", "failed", "expired", "cancelled")


class ProviderOperationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def reserve(
        self,
        *,
        provider: str,
        operation_type: str,
        place_id: UUID | None,
        idempotency_key: str,
        request_fingerprint: str,
        requested_units: int,
        snapshot: SerpApiAccountSnapshot | None,
        reviewer_id: UUID | None = None,
    ) -> tuple[ProviderOperation, bool]:
        """Create an atomic reservation or return an idempotent replay.

        The caller must make no paid provider request before this method returns.
        """
        plan_period = _plan_period(snapshot)
        now = datetime.now(timezone.utc)
        await self.session.rollback()
        async with self.session.begin():
            await self.session.execute(
                insert(ProviderBudgetPeriod)
                .values(
                    provider=provider,
                    plan_period=plan_period,
                    configured_local_budget=settings.serpapi_monthly_request_budget,
                )
                .on_conflict_do_nothing(index_elements=["provider", "plan_period"])
            )
            period = (
                await self.session.execute(
                    select(ProviderBudgetPeriod)
                    .where(
                        ProviderBudgetPeriod.provider == provider,
                        ProviderBudgetPeriod.plan_period == plan_period,
                    )
                    .with_for_update()
                )
            ).scalar_one()
            if snapshot is not None:
                period.configured_local_budget = settings.serpapi_monthly_request_budget
                period.provider_reported_remaining = snapshot.total_searches_left
                period.provider_hourly_used = snapshot.this_hour_searches
                period.provider_hourly_limit = snapshot.account_rate_limit_per_hour
                period.plan_renewal_date = snapshot.plan_renewal_date
                period.snapshot_fetched_at = snapshot.fetched_at

            await self._expire_leases(provider, plan_period, now)
            existing = (
                await self.session.execute(
                    select(ProviderOperation)
                    .where(
                        ProviderOperation.provider == provider,
                        ProviderOperation.plan_period == plan_period,
                        ProviderOperation.idempotency_key == idempotency_key,
                    )
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if existing is not None:
                if existing.request_fingerprint != request_fingerprint:
                    raise AppError("IDEMPOTENCY_CONFLICT", "Idempotency key was used with different parameters.", 409)
                await self._expire_if_needed(existing, now)
                return existing, True

            if reviewer_id is not None:
                reviewer = (
                    await self.session.execute(select(Reviewer).where(Reviewer.id == reviewer_id).with_for_update())
                ).scalar_one_or_none()
                if reviewer is None:
                    raise AppError("REVIEWER_NOT_FOUND", "Reviewer was not found.", 404)
                active_for_reviewer = (
                    await self.session.execute(
                        select(ProviderOperation)
                        .where(
                            ProviderOperation.reviewer_id == reviewer_id,
                            ProviderOperation.provider == provider,
                            ProviderOperation.status.in_(ACTIVE_STATUSES),
                        )
                        .with_for_update()
                    )
                ).scalars().all()
                for operation in active_for_reviewer:
                    await self._expire_if_needed(operation, now)
                    if operation.status in ACTIVE_STATUSES:
                        raise AppError(
                            "REVIEWER_CONTEXT_ALREADY_RUNNING",
                            "A reviewer context operation is already running.",
                            409,
                            {"operation_id": str(operation.id), "status": operation.status},
                        )

            active_for_place = (
                await self.session.execute(
                    select(ProviderOperation)
                    .where(
                        ProviderOperation.place_id == place_id,
                        ProviderOperation.provider == provider,
                        ProviderOperation.status.in_(ACTIVE_STATUSES),
                    )
                    .order_by(ProviderOperation.created_at.desc())
                    .with_for_update()
                )
            ).scalars().all() if place_id else []
            for operation in active_for_place:
                await self._expire_if_needed(operation, now)
                if operation.status in ACTIVE_STATUSES:
                    raise AppError(
                        "SYNC_ALREADY_RUNNING",
                        "A review operation is already running for this restaurant.",
                        409,
                        {"operation_id": str(operation.id), "status": operation.status},
                    )

            await self._assert_capacity(period, requested_units, now)
            operation = ProviderOperation(
                provider=provider,
                plan_period=plan_period,
                operation_type=operation_type,
                place_id=place_id,
                reviewer_id=reviewer_id,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                requested_units=requested_units,
                status="reserved",
                lease_expires_at=now + timedelta(seconds=settings.provider_reservation_lease_seconds),
            )
            self.session.add(operation)
            await self.session.flush()
            return operation, False

    async def reclaim_if_expired(self, operation: ProviderOperation) -> None:
        await self._expire_if_needed(operation, datetime.now(timezone.utc))
        await self.session.commit()

    async def mark_running(self, operation: ProviderOperation) -> None:
        operation.status = "running"
        await self.heartbeat(operation)
        await self.session.commit()

    async def heartbeat(self, operation: ProviderOperation) -> None:
        operation.lease_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.provider_reservation_lease_seconds
        )
        await self.session.flush()

    async def settle_page(
        self,
        operation: ProviderOperation,
        *,
        successful: int = 0,
        cached: int = 0,
        failed: int = 0,
        uncertain: int = 0,
        collected: int = 0,
    ) -> None:
        operation.successful_request_count += successful
        operation.cached_response_count += cached
        operation.failed_request_count += failed
        operation.uncertain_request_count += uncertain
        operation.collected_unique_count += collected
        await self.heartbeat(operation)
        await self.session.flush()

    async def finish(
        self,
        operation: ProviderOperation,
        *,
        status: str,
        stop_reason: str | None = None,
        error_summary: str | None = None,
    ) -> None:
        await self.session.refresh(operation)
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Unsupported terminal operation status: {status}")
        operation.status = status
        operation.stop_reason = stop_reason
        operation.error_summary = error_summary
        operation.completed_at = datetime.now(timezone.utc)
        operation.released_reserved_count = max(
            0,
            operation.requested_units
            - operation.successful_request_count
            - operation.uncertain_request_count,
        )
        await self.session.flush()
        await self.session.commit()

    async def cancellation_requested(self, operation_id: UUID) -> bool:
        operation = await self.get(operation_id)
        return operation is not None and operation.cancel_requested_at is not None

    async def request_cancel(self, operation_id: UUID) -> ProviderOperation | None:
        operation = await self.get_for_update(operation_id)
        if operation is None:
            return None
        if operation.status in ACTIVE_STATUSES and operation.cancel_requested_at is None:
            operation.cancel_requested_at = datetime.now(timezone.utc)
            await self.session.commit()
        return operation

    async def find_by_idempotency(
        self, provider: str, idempotency_key: str
    ) -> ProviderOperation | None:
        return (
            await self.session.execute(
                select(ProviderOperation)
                .where(
                    ProviderOperation.provider == provider,
                    ProviderOperation.idempotency_key == idempotency_key,
                )
                .order_by(ProviderOperation.created_at.desc())
                .limit(1)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def get(self, operation_id: UUID) -> ProviderOperation | None:
        return (
            await self.session.execute(
                select(ProviderOperation)
                .where(ProviderOperation.id == operation_id)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def get_for_update(self, operation_id: UUID) -> ProviderOperation | None:
        return (
            await self.session.execute(
                select(ProviderOperation).where(ProviderOperation.id == operation_id).with_for_update()
            )
        ).scalar_one_or_none()

    async def list_recent(self, limit: int) -> list[ProviderOperation]:
        result = await self.session.execute(
            select(ProviderOperation)
            .order_by(ProviderOperation.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def remaining_for_provider(self, provider: str) -> int:
        period = _plan_period(None)
        settled, active = await self._local_usage(provider, period)
        return max(0, settings.serpapi_monthly_request_budget - settled - active)

    async def active_for_place(self, provider: str, place_id: UUID) -> ProviderOperation | None:
        return (await self.session.execute(
            select(ProviderOperation).where(
                ProviderOperation.provider == provider,
                ProviderOperation.place_id == place_id,
                ProviderOperation.status.in_(ACTIVE_STATUSES),
            ).order_by(ProviderOperation.created_at.desc()).limit(1)
        )).scalar_one_or_none()

    async def remaining_local_budget(self, operation: ProviderOperation) -> int:
        period = (
            await self.session.execute(
                select(ProviderBudgetPeriod).where(
                    ProviderBudgetPeriod.provider == operation.provider,
                    ProviderBudgetPeriod.plan_period == operation.plan_period,
                )
            )
        ).scalar_one_or_none()
        if period is None:
            return 0
        settled, active = await self._local_usage(operation.provider, operation.plan_period)
        return max(0, period.configured_local_budget - settled - active)

    async def _assert_capacity(
        self, period: ProviderBudgetPeriod, requested_units: int, now: datetime
    ) -> None:
        local_consumed, active_reserved = await self._local_usage(period.provider, period.plan_period)
        local_remaining = period.configured_local_budget - local_consumed - active_reserved

        provider_remaining = None
        if period.provider_reported_remaining is not None:
            consumed_since_snapshot = await self._reserved_or_consumed_since(
                period.provider, period.plan_period, period.snapshot_fetched_at
            )
            provider_remaining = period.provider_reported_remaining - consumed_since_snapshot

        effective_remaining = min(
            local_remaining,
            provider_remaining if provider_remaining is not None else local_remaining,
        )
        if effective_remaining < requested_units:
            raise AppError("PROVIDER_BUDGET_EXHAUSTED", "Insufficient unreserved SerpApi budget.", 429)

        hourly_limit = _hourly_limit(period)
        if hourly_limit is not None:
            local_hourly, active_hourly = await self._local_usage(
                period.provider, period.plan_period, now - timedelta(hours=1)
            )
            reported_hourly = period.provider_hourly_used or 0
            snapshot_reserved = await self._reserved_or_consumed_since(
                period.provider, period.plan_period, period.snapshot_fetched_at
            )
            hourly_remaining = min(
                hourly_limit - local_hourly - active_hourly,
                hourly_limit - reported_hourly - snapshot_reserved,
            )
            if hourly_remaining < requested_units:
                raise AppError("PROVIDER_HOURLY_LIMIT_REACHED", "SerpApi hourly safety limit reached.", 429)

    async def _local_usage(
        self, provider: str, plan_period: str, since: datetime | None = None
    ) -> tuple[int, int]:
        conditions = [
            ProviderOperation.provider == provider,
            ProviderOperation.plan_period == plan_period,
        ]
        if since is not None:
            conditions.append(ProviderOperation.created_at >= since)
        settled = func.coalesce(
            func.sum(ProviderOperation.successful_request_count + ProviderOperation.uncertain_request_count), 0
        )
        active = func.coalesce(
            func.sum(case((ProviderOperation.status.in_(ACTIVE_STATUSES), ProviderOperation.requested_units), else_=0)),
            0,
        )
        row = (await self.session.execute(select(settled, active).where(*conditions))).one()
        return int(row[0]), int(row[1])

    async def _reserved_or_consumed_since(
        self, provider: str, plan_period: str, since: datetime | None
    ) -> int:
        if since is None:
            return 0
        consumed = case(
            (ProviderOperation.status.in_(ACTIVE_STATUSES), ProviderOperation.requested_units),
            else_=ProviderOperation.successful_request_count + ProviderOperation.uncertain_request_count,
        )
        result = await self.session.execute(
            select(func.coalesce(func.sum(consumed), 0)).where(
                ProviderOperation.provider == provider,
                ProviderOperation.plan_period == plan_period,
                ProviderOperation.created_at >= since,
            )
        )
        return int(result.scalar_one())

    async def _expire_leases(self, provider: str, plan_period: str, now: datetime) -> None:
        operations = (
            await self.session.execute(
                select(ProviderOperation)
                .where(
                    ProviderOperation.provider == provider,
                    ProviderOperation.plan_period == plan_period,
                    ProviderOperation.status.in_(ACTIVE_STATUSES),
                    ProviderOperation.lease_expires_at <= now,
                )
                .with_for_update()
            )
        ).scalars().all()
        for operation in operations:
            await self._expire_if_needed(operation, now)

    async def _expire_if_needed(self, operation: ProviderOperation, now: datetime) -> None:
        if operation.status in ACTIVE_STATUSES and operation.lease_expires_at <= now:
            operation.status = "expired"
            operation.stop_reason = "lease_expired"
            operation.completed_at = now
            operation.released_reserved_count = max(
                0,
                operation.requested_units
                - operation.successful_request_count
                - operation.uncertain_request_count,
            )
            await self.session.flush()


def _plan_period(snapshot: SerpApiAccountSnapshot | None) -> str:
    if snapshot and snapshot.plan_renewal_date:
        return f"renews-{snapshot.plan_renewal_date.isoformat()}"
    return current_plan_period()


def _hourly_limit(period: ProviderBudgetPeriod) -> int | None:
    limits = [value for value in (settings.provider_hourly_request_limit, period.provider_hourly_limit) if value]
    return min(limits) if limits else None
