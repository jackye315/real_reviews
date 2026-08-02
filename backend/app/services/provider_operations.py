from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.place import Place
from app.models.provider_operation import ProviderOperation
from app.models.reviewer import Reviewer
from app.providers.serpapi_account import SerpApiAccountClient, SerpApiAccountSnapshot
from app.repositories.provider_operations import ProviderOperationRepository
from app.schemas.operations import ProviderOperationResponse

_snapshot_cache: tuple[SerpApiAccountSnapshot, float] | None = None
_snapshot_lock = asyncio.Lock()
_serpapi_semaphore: asyncio.Semaphore | None = None


async def account_snapshot() -> SerpApiAccountSnapshot | None:
    global _snapshot_cache
    now = time.monotonic()
    if _snapshot_cache and now - _snapshot_cache[1] < settings.serpapi_account_snapshot_ttl_seconds:
        return _snapshot_cache[0]
    async with _snapshot_lock:
        now = time.monotonic()
        if _snapshot_cache and now - _snapshot_cache[1] < settings.serpapi_account_snapshot_ttl_seconds:
            return _snapshot_cache[0]
        try:
            snapshot = await SerpApiAccountClient().fetch_snapshot()
        except Exception:
            # Operations fall back to the latest valid snapshot or local accounting.
            return _snapshot_cache[0] if _snapshot_cache else None
        _snapshot_cache = (snapshot, now)
        return snapshot


def serpapi_semaphore() -> asyncio.Semaphore:
    global _serpapi_semaphore
    if _serpapi_semaphore is None:
        _serpapi_semaphore = asyncio.Semaphore(settings.serpapi_max_concurrency)
    return _serpapi_semaphore


@dataclass(slots=True)
class OperationView:
    response: ProviderOperationResponse
    is_running: bool


class ProviderOperationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ProviderOperationRepository(session)

    async def view(self, operation: ProviderOperation, *, include_reviewer_context: bool = True) -> ProviderOperationResponse:
        place = None
        if operation.place_id is not None:
            place = (
                await self.session.execute(select(Place).where(Place.id == operation.place_id))
            ).scalar_one_or_none()
        reviewer = None
        reviewer_id = getattr(operation, "reviewer_id", None)
        if reviewer_id is not None:
            reviewer = (
                await self.session.execute(select(Reviewer).where(Reviewer.id == reviewer_id))
            ).scalar_one_or_none()
        metadata = operation.result_metadata or {}
        return ProviderOperationResponse(
            operation_id=operation.id,
            provider=operation.provider,
            operation_type=operation.operation_type,
            place_id=place.google_place_id if place else None,
            restaurant_name=place.display_name if place else None,
            reviewer_id=reviewer.id if reviewer else None,
            reviewer_name=reviewer.display_name if reviewer else None,
            status=operation.status,
            estimated_request_count=operation.requested_units,
            reserved_request_count=max(0, operation.requested_units - operation.released_reserved_count),
            successful_request_count=operation.successful_request_count,
            cached_response_count=operation.cached_response_count,
            failed_request_count=operation.failed_request_count,
            uncertain_request_count=operation.uncertain_request_count,
            released_reserved_count=operation.released_reserved_count,
            collected_unique_count=operation.collected_unique_count,
            remaining_local_budget=await self.repository.remaining_local_budget(operation),
            stop_reason=operation.stop_reason,
            error_code=metadata.get("error_code"),
            recovery_available=bool(metadata.get("recovery_available")),
            recovery_estimated_request_count=metadata.get("recovery_estimated_request_count"),
            provider_sort=metadata.get("provider_sort"),
            requested_provider_record_count=metadata.get("requested_provider_record_count"),
            processed_provider_record_count=metadata.get("processed_provider_record_count"),
            new_canonical_review_count=metadata.get("new_canonical_review_count"),
            updated_existing_review_count=metadata.get("updated_existing_review_count"),
            unchanged_review_count=metadata.get("unchanged_review_count"),
            total_stored_review_count=metadata.get("total_stored_review_count"),
            recovery_scanned_record_count=metadata.get("recovery_scanned_record_count"),
            provider_results_returned=metadata.get("provider_results_returned"),
            accepted_food_and_drink_count=metadata.get("accepted_food_and_drink_count"),
            rejected_non_food_count=metadata.get("rejected_non_food_count"),
            rejected_unknown_type_count=metadata.get("rejected_unknown_type_count"),
            rejected_missing_required_data_count=metadata.get("rejected_missing_required_data_count"),
            duplicate_result_count=metadata.get("duplicate_result_count"),
            context_generation=metadata.get("context_generation"),
            reviewer_context=metadata.get("reviewer_context") if include_reviewer_context else None,
            cancel_requested_at=operation.cancel_requested_at,
            created_at=operation.created_at,
            updated_at=operation.updated_at,
            completed_at=operation.completed_at,
        )

    async def get(self, operation_id) -> ProviderOperationResponse | None:
        operation = await self.repository.get(operation_id)
        return await self.view(operation) if operation else None

    async def list_recent(self, limit: int) -> list[ProviderOperationResponse]:
        return [await self.view(operation, include_reviewer_context=False) for operation in await self.repository.list_recent(limit)]

    async def request_cancel(self, operation_id) -> ProviderOperationResponse | None:
        operation = await self.repository.request_cancel(operation_id)
        return await self.view(operation) if operation else None

