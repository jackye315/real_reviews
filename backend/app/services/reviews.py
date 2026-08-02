from __future__ import annotations

import asyncio
import hashlib
import json

import httpx
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.db.base import utcnow
from app.db.session import AsyncSessionLocal
from app.models.place import Place
from app.models.review import Review
from app.models.review_collection_state import ReviewCollectionState
from app.models.review_relevance_rank import ReviewRelevanceRank
from app.providers.base import ReviewProvider
from app.providers.google_places import GooglePlacesReviewProvider
from app.providers.serpapi import ProviderCursorExpiredError, SerpApiReviewProvider
from app.repositories.places import PlaceRepository
from app.repositories.provider_operations import ProviderOperationRepository
from app.repositories.reviews import ReviewRepository
from app.repositories.usage import UsageRepository
from app.schemas.operations import ProviderOperationResponse
from app.services.provider_operations import (
    ProviderOperationService,
    account_snapshot,
    serpapi_semaphore,
)
from app.schemas.reviews import (
    LoadMoreChoiceResponse,
    LoadMoreOptionsResponse,
    LoadMoreRequest,
    ReviewImageResponse,
    ReviewListResponse,
    ReviewResponse,
    ReviewSort,
    ReviewSyncRequest,
    ReviewSyncResponse,
    ReviewTopicResponse,
)
from app.utils.review_cursors import decode_cursor, encode_cursor
from uuid import uuid4


def estimate_serpapi_requests(target_count: int) -> int:
    if target_count <= 8:
        return 1
    return 1 + ((target_count - 8 + 19) // 20)


def estimate_load_more_requests(target_count: int) -> int:
    return (target_count + 19) // 20


def _sync_fingerprint(place_id: str, request: ReviewSyncRequest, is_refresh: bool, operation_type: str | None = None) -> str:
    payload = json.dumps(
        {
            "place_id": place_id,
            "operation": operation_type or ("refresh" if is_refresh else "sync"),
            "target_count": request.target_count,
            "force": request.force,
            "cursor": request.cursor,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def topic_to_response(topic) -> ReviewTopicResponse:
    return ReviewTopicResponse(
        provider_topic_id=topic.provider_topic_id,
        keyword=topic.keyword,
        mentions=topic.mentions,
        language_code=topic.language_code,
        rank=topic.rank,
    )


def review_to_response(review: Review) -> ReviewResponse:
    origins = getattr(review, "origins", []) or []
    labels = sorted({origin.source_label or origin.provider_name for origin in origins})
    return ReviewResponse(
        id=review.id,
        rating=review.rating,
        text=review.text,
        original_text=review.original_text,
        publication_timestamp=review.publication_timestamp,
        last_edit_timestamp=review.last_edit_timestamp,
        canonical_source_url=review.canonical_source_url,
        author_display_name=review.author_display_name,
        author_avatar_url=review.author_avatar_url,
        reviewer_id=review.reviewer_id,
        source_labels=labels,
        details=review.details or {},
        translated_details=review.translated_details or {},
        images=[
            ReviewImageResponse(url=image.provider_image_url, position=image.position, provider=image.provider_name)
            for image in sorted(
                (image for image in getattr(review, "images", []) or [] if image.active),
                key=lambda image: (image.position, str(image.id)),
            )
        ],
        first_fetched_at=review.first_fetched_at,
        last_seen_at=review.last_seen_at,
        suspected_duplicate=review.suspected_duplicate,
    )


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.places = PlaceRepository(session)
        self.reviews = ReviewRepository(session)
        self.usage = UsageRepository(session)

    async def list_reviews(
        self,
        place_id: str,
        rating: int | None = None,
        sort: ReviewSort | None = None,
        page_size: int = 20,
        cursor: str | None = None,
    ) -> ReviewListResponse:
        place = await self._get_place(place_id)
        relevance_state = await self._collection_state(place, "qualityScore")
        snapshot_id = relevance_state.active_snapshot_id if relevance_state else None
        requested_sort = sort or (ReviewSort.RELEVANT if snapshot_id else ReviewSort.RECENT)
        effective_sort = requested_sort if requested_sort != ReviewSort.RELEVANT or snapshot_id else ReviewSort.RECENT
        decoded = decode_cursor(cursor, place_id=place_id, rating=rating, sort=requested_sort, version=place.review_corpus_version) if cursor else None
        rows = await self.reviews.list_page_for_place(place, rating, effective_sort, page_size, decoded, snapshot_id)
        has_more = len(rows) > page_size
        reviews = rows[:page_size]
        total = await self.reviews.count_for_place(place)
        filtered_total = await self.reviews.count_for_place(place, rating=rating)
        topics = await self.reviews.list_topics_for_place(place)
        return ReviewListResponse(
            reviews=[review_to_response(item) for item in reviews],
            page_size=page_size,
            next_cursor=encode_cursor(place_id, rating, requested_sort, place.review_corpus_version, reviews[-1], await self.reviews.relevance_rank_for_review(place, snapshot_id, reviews[-1].id) if requested_sort == ReviewSort.RELEVANT else None) if has_more and reviews else None,
            has_more=has_more,
            review_corpus_version=place.review_corpus_version,
            total=total,
            filtered_total=filtered_total,
            topics=[topic_to_response(item) for item in topics],
            topics_fetched_at=max((item.snapshot_fetched_at for item in topics), default=None),
            relevance_available=bool(snapshot_id),
            relevance_fetched_at=relevance_state.relevance_fetched_at if relevance_state else None,
            relevance_ranked_count=relevance_state.ranked_count if relevance_state else 0,
            relevance_status=relevance_state.snapshot_status if relevance_state else None,
        )

    async def sync(
        self, place_id: str, request: ReviewSyncRequest, idempotency_key: str | None = None
    ) -> ReviewSyncResponse | ProviderOperationResponse:
        return await self._sync(place_id, request, is_refresh=False, idempotency_key=idempotency_key)

    async def start_sync(
        self, place_id: str, request: ReviewSyncRequest, idempotency_key: str | None = None
    ) -> ReviewSyncResponse | ProviderOperationResponse:
        return await self._start_paid_sync(place_id, request, is_refresh=False, idempotency_key=idempotency_key)

    async def load_more_options(self, place_id: str) -> LoadMoreOptionsResponse:
        place = await self._get_place(place_id)
        state = await self._collection_state(place)
        remaining = await ProviderOperationRepository(self.session).remaining_for_provider(settings.review_provider)
        active = await ProviderOperationRepository(self.session).active_for_place(settings.review_provider, place.id)
        cursor_available = bool(state and state.pagination_cursor)
        return LoadMoreOptionsResponse(
            cursor_available=cursor_available,
            active_operation_id=str(active.id) if active else None,
            remaining_effective_budget=remaining,
            choices=[
                LoadMoreChoiceResponse(provider_record_count=count, estimated_request_count=estimate_load_more_requests(count), allowed=cursor_available and active is None and estimate_load_more_requests(count) <= remaining)
                for count in (20, 50, 100)
            ],
        )

    async def start_load_more(self, place_id: str, request: LoadMoreRequest, idempotency_key: str | None) -> ProviderOperationResponse:
        place = await self._get_place(place_id)
        state = await self._collection_state(place)
        if not request.restart_from_newest and not (state and state.pagination_cursor):
            raise AppError("NO_PROVIDER_CURSOR", "No resumable provider cursor is available.", 409)
        cursor = None if request.restart_from_newest else state.pagination_cursor
        target = request.additional_target_count
        sync_request = ReviewSyncRequest(target_count=target, force=True, confirm_cost=request.confirm_cost, cursor=cursor)
        result = await self._start_paid_sync(place_id, sync_request, False, idempotency_key, operation_type="load_more")
        if not isinstance(result, ProviderOperationResponse):
            raise AppError("LOAD_MORE_UNEXPECTED_RESULT", "Load-more did not create an operation.", 500)
        return result

    async def start_check_new(
        self, place_id: str, request: ReviewSyncRequest, idempotency_key: str | None = None
    ) -> ReviewSyncResponse | ProviderOperationResponse:
        return await self._start_paid_sync(
            place_id,
            request.model_copy(update={"force": True}),
            is_refresh=True,
            idempotency_key=idempotency_key,
            operation_type="check_new_reviews",
        )

    async def start_refresh(
        self, place_id: str, request: ReviewSyncRequest, idempotency_key: str | None = None
    ) -> ReviewSyncResponse | ProviderOperationResponse:
        return await self._start_paid_sync(
            place_id,
            request.model_copy(update={"force": True}),
            is_refresh=True,
            idempotency_key=idempotency_key,
        )

    async def _start_paid_sync(
        self,
        place_id: str,
        request: ReviewSyncRequest,
        is_refresh: bool,
        idempotency_key: str | None,
        operation_type: str | None = None,
    ) -> ReviewSyncResponse | ProviderOperationResponse:
        result = await self._sync(
            place_id,
            request,
            is_refresh,
            idempotency_key,
            reserve_only=True,
            operation_type=operation_type,
        )
        if isinstance(result, ProviderOperationResponse) and result.status in {"reserved", "running"}:
            asyncio.create_task(
                self._run_reserved_sync(place_id, request, is_refresh, idempotency_key, operation_type),
                name=f"provider-operation-{result.operation_id}",
            )
        return result

    @staticmethod
    async def _run_reserved_sync(
        place_id: str,
        request: ReviewSyncRequest,
        is_refresh: bool,
        idempotency_key: str | None,
        operation_type: str | None = None,
    ) -> None:
        async with AsyncSessionLocal() as session:
            try:
                await ReviewService(session)._sync(
                    place_id,
                    request,
                    is_refresh,
                    idempotency_key,
                    execute_existing_operation=True,
                    operation_type=operation_type,
                )
            except Exception:
                # The operation record contains a sanitized terminal failure summary.
                return

    async def _sync(
        self,
        place_id: str,
        request: ReviewSyncRequest,
        is_refresh: bool,
        idempotency_key: str | None = None,
        *,
        reserve_only: bool = False,
        execute_existing_operation: bool = False,
        operation_type: str | None = None,
    ) -> ReviewSyncResponse | ProviderOperationResponse:
        place = await self._get_place(place_id)
        operation_repository = ProviderOperationRepository(self.session)
        if idempotency_key and not execute_existing_operation:
            replay = await operation_repository.find_by_idempotency(
                settings.review_provider, idempotency_key
            )
            if replay is not None:
                if replay.request_fingerprint != _sync_fingerprint(place_id, request, is_refresh, operation_type):
                    raise AppError("IDEMPOTENCY_CONFLICT", "Idempotency key was used with different parameters.", 409)
                await operation_repository.reclaim_if_expired(replay)
                return await ProviderOperationService(self.session).view(replay)
        existing = await self.reviews.list_for_place(place)
        if existing and not request.force and not execute_existing_operation:
            topics = await self.reviews.list_topics_for_place(place)
            return ReviewSyncResponse(
                place_id=place_id,
                status="cached",
                collected_unique_count=len(existing),
                successful_request_count=0,
                reviews=[review_to_response(item) for item in existing],
                topics=[topic_to_response(item) for item in topics],
                topics_fetched_at=max((item.snapshot_fetched_at for item in topics), default=None),
                message="Using stored reviews. Pass force=true to fetch again.",
            )

        target = request.target_count or settings.serpapi_default_review_limit
        estimated_requests = estimate_load_more_requests(target) if operation_type == "load_more" and request.cursor else estimate_serpapi_requests(target)
        if not request.confirm_cost:
            raise AppError(
                "COST_CONFIRMATION_REQUIRED",
                f"This will contact SerpApi and may use approximately {estimated_requests} searches. Set confirm_cost=true to continue.",
                409,
            )
        if not idempotency_key:
            raise AppError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required for paid review operations.", 400)

        operation, replayed = await operation_repository.reserve(
            provider=settings.review_provider,
            operation_type=operation_type or ("refresh" if is_refresh else "sync"),
            place_id=place.id,
            idempotency_key=idempotency_key,
            request_fingerprint=_sync_fingerprint(place_id, request, is_refresh, operation_type),
            requested_units=estimated_requests,
            snapshot=await account_snapshot(),
        )
        operation_service = ProviderOperationService(self.session)
        if reserve_only or (replayed and not execute_existing_operation):
            return await operation_service.view(operation)

        lock_acquired = await self._try_place_lock(place.google_place_id)
        if not lock_acquired:
            active = await operation_repository.get(operation.id)
            if active is not None and active.status in {"reserved", "running"}:
                return await operation_service.view(active)
            raise AppError(
                "SYNC_ALREADY_RUNNING",
                "A review operation is already running for this restaurant.",
                409,
            )

        if operation.status == "running":
            await self._release_place_lock(place.google_place_id)
            await self.session.commit()
            return await operation_service.view(operation)
        run = await self.reviews.create_sync_run(place, settings.review_provider, target)
        await operation_repository.mark_running(operation)
        await self.session.commit()
        provider = self._review_provider(settings.review_provider)
        fallback = self._review_provider(settings.review_fallback_provider)
        provider_sort = "newestFirst" if operation_type == "check_new_reviews" else settings.serpapi_review_sort
        relevance_state = await self._collection_state(place, provider_sort) if provider_sort == "qualityScore" else None
        previous_snapshot_id = relevance_state.active_snapshot_id if relevance_state else None
        snapshot_id = relevance_state.pending_snapshot_id if relevance_state and request.cursor else None
        if provider_sort == "qualityScore" and snapshot_id is None:
            snapshot_id = uuid4()
            if relevance_state is None:
                relevance_state = await self._store_provider_cursor(place, None, provider_sort)
            relevance_state.pending_snapshot_id = snapshot_id
            relevance_state.next_rank = 1
            relevance_state.ranked_count = 0
            await self.session.flush()
        cursor: str | None = request.cursor
        collected = 0
        processed = 0
        updated = 0
        unchanged = 0
        successful = 0
        fallback_used = False
        status = "completed"
        error: str | None = None
        stop_reason: str | None = None
        known_streak = 0
        topic_field_observed = False
        topic_count_observed = 0
        known_streak_limit = (
            settings.refresh_known_streak_limit if provider_sort == "newestFirst" and is_refresh and request.cursor is None else 0
        )

        try:
            while processed < target:
                if await operation_repository.cancellation_requested(operation.id):
                    status = "cancelled"
                    stop_reason = "user_cancelled"
                    break
                await operation_repository.heartbeat(operation)
                await self.session.commit()
                page_size = min(20, target - processed)
                page_from_fallback = False
                try:
                    async with serpapi_semaphore():
                        page = await provider.fetch_page(
                            place.google_place_id, cursor, page_size, provider_sort
                        )
                except ProviderCursorExpiredError:
                    raise
                except Exception as exc:
                    uncertain = int(isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)))
                    await operation_repository.settle_page(
                        operation,
                        failed=0 if uncertain else 1,
                        uncertain=uncertain,
                    )
                    if uncertain:
                        error = f"Primary provider outcome uncertain: {type(exc).__name__}"
                    else:
                        await self.usage.increment(settings.review_provider, failed=1)
                    await self.session.commit()
                    if processed > 0:
                        raise
                    page = await fallback.fetch_page(
                        place.google_place_id, None, min(5, page_size), provider_sort
                    )
                    page_from_fallback = True
                    fallback_used = True
                    error = error or f"Primary review provider failed; used fallback: {type(exc).__name__}"

                if not page.reviews and processed == 0 and not page_from_fallback:
                    if page.cached:
                        await self.usage.increment(settings.review_provider, cached=1)
                        await operation_repository.settle_page(operation, cached=1)
                    else:
                        await self.usage.increment(
                            settings.review_provider, successful=page.successful_request_count
                        )
                        await operation_repository.settle_page(
                            operation, successful=page.successful_request_count
                        )
                        successful += page.successful_request_count
                    await self.session.commit()
                    page = await fallback.fetch_page(
                        place.google_place_id, None, min(5, page_size), provider_sort
                    )
                    page_from_fallback = True
                    fallback_used = True
                    error = "Primary review provider returned no reviews; used fallback."

                usage_provider = settings.review_fallback_provider if page_from_fallback else settings.review_provider
                if page.topics is not None and not page_from_fallback and provider_sort == "qualityScore":
                    topic_field_observed = True
                    topic_count_observed = len(page.topics)
                    await self.reviews.upsert_topic_snapshot(
                        place, usage_provider, page.topics, settings.serpapi_language or None
                    )
                if page.cached:
                    await self.usage.increment(usage_provider, cached=1)
                    if not page_from_fallback:
                        await operation_repository.settle_page(operation, cached=1)
                else:
                    await self.usage.increment(usage_provider, successful=page.successful_request_count)
                    if not page_from_fallback:
                        await operation_repository.settle_page(
                            operation, successful=page.successful_request_count
                        )
                        successful += page.successful_request_count
                if not page.reviews:
                    await self.session.commit()
                    break
                collected_before_page = collected
                corpus_changed = False
                for item in page.reviews:
                    review, outcome = await self.reviews.upsert_normalized(place, item)
                    if provider_sort == "qualityScore" and not page_from_fallback and snapshot_id is not None:
                        await self._store_relevance_rank(place, review, snapshot_id, relevance_state.next_rank)
                        relevance_state.next_rank += 1
                        relevance_state.ranked_count += 1
                    processed += 1
                    if outcome == "created":
                        collected += 1
                        corpus_changed = True
                    elif outcome == "changed":
                        updated += 1
                        corpus_changed = True
                    else:
                        unchanged += 1
                    if outcome == "unchanged":
                        known_streak += 1
                    else:
                        known_streak = 0
                if corpus_changed:
                    await self.reviews.increment_corpus_version(place)
                await operation_repository.settle_page(
                    operation, collected=collected - collected_before_page
                )
                cursor = page.next_cursor
                if not page_from_fallback:
                    relevance_state = await self._store_provider_cursor(place, cursor, provider_sort)
                    if provider_sort == "qualityScore" and snapshot_id is not None and relevance_state.active_snapshot_id is None:
                        relevance_state.active_snapshot_id = snapshot_id
                        relevance_state.snapshot_status = "complete" if not cursor else "partial"
                        relevance_state.relevance_fetched_at = utcnow()
                should_stop_after_page = page_from_fallback or not cursor
                if not cursor:
                    stop_reason = "pagination_ended"
                if known_streak_limit and known_streak >= known_streak_limit and cursor:
                    stop_reason = "known_unchanged_streak"
                    should_stop_after_page = True
                await self.reviews.complete_sync_run(
                    run,
                    "running",
                    collected,
                    successful,
                    cursor,
                    error,
                    stop_reason,
                    topic_field_observed,
                    topic_count_observed,
                )
                await self.session.commit()
                if await operation_repository.cancellation_requested(operation.id):
                    status = "cancelled"
                    stop_reason = "user_cancelled"
                    break
                if should_stop_after_page:
                    break
            if status == "cancelled":
                if provider_sort == "qualityScore" and previous_snapshot_id is not None and snapshot_id is not None:
                    await self._discard_unactivated_relevance_snapshot(place, relevance_state, snapshot_id)
            elif processed < target and cursor:
                status = "partial"
            elif processed >= target and cursor:
                stop_reason = stop_reason or "target_reached"
            if provider_sort == "qualityScore" and relevance_state is not None and snapshot_id is not None and status != "cancelled":
                complete_replacement = not cursor or processed >= target
                if previous_snapshot_id is not None and previous_snapshot_id != snapshot_id and complete_replacement:
                    await self.session.execute(delete(ReviewRelevanceRank).where(
                        ReviewRelevanceRank.place_id == place.id,
                        ReviewRelevanceRank.snapshot_id == previous_snapshot_id,
                    ))
                    relevance_state.active_snapshot_id = snapshot_id
                relevance_state.pending_snapshot_id = snapshot_id if cursor else None
                relevance_state.snapshot_status = "complete" if not cursor else "partial"
                relevance_state.relevance_fetched_at = utcnow()
                await self.reviews.increment_corpus_version(place)
            await self.reviews.complete_sync_run(
                run,
                status,
                collected,
                successful,
                cursor,
                error,
                stop_reason,
                topic_field_observed,
                topic_count_observed,
            )
            operation.result_metadata = {
                "provider_sort": provider_sort,
                "requested_provider_record_count": target,
                "processed_provider_record_count": processed,
                "new_canonical_review_count": collected,
                "updated_existing_review_count": updated,
                "unchanged_review_count": unchanged,
                "total_stored_review_count": await self.reviews.count_for_place(place),
            }
            await self.session.flush()
            await self.session.commit()
            await operation_repository.finish(
                operation,
                status="cancelled" if status == "cancelled" else "completed",
                stop_reason=stop_reason,
                error_summary=error,
            )
        except ProviderCursorExpiredError:
            await self.session.rollback()
            if provider_sort == "qualityScore" and previous_snapshot_id is not None and snapshot_id is not None:
                await self._discard_unactivated_relevance_snapshot(place, relevance_state, snapshot_id)
            await self.reviews.complete_sync_run(run, "failed", collected, successful, cursor, "PROVIDER_CURSOR_EXPIRED", "provider_cursor_expired")
            await self.session.commit()
            await self.session.refresh(operation)
            operation.result_metadata = {"error_code": "PROVIDER_CURSOR_EXPIRED", "recovery_available": True, "recovery_estimated_request_count": operation.requested_units}
            await self.session.flush()
            await operation_repository.finish(operation, status="failed", stop_reason="provider_cursor_expired", error_summary="PROVIDER_CURSOR_EXPIRED")
            return await self._operation_result(place_id, place, operation, "failed", collected, successful, cursor, False, "The provider cursor expired.", "provider_cursor_expired")
        except Exception as exc:
            await self.session.rollback()
            if provider_sort == "qualityScore" and previous_snapshot_id is not None and snapshot_id is not None:
                await self._discard_unactivated_relevance_snapshot(place, relevance_state, snapshot_id)
            await self.reviews.complete_sync_run(
                run, "failed", collected, successful, cursor, type(exc).__name__, "error"
            )
            await self.session.commit()
            await operation_repository.finish(
                operation, status="failed", stop_reason="error", error_summary=type(exc).__name__
            )
            raise
        finally:
            await self._release_place_lock(place.google_place_id)
            await self.session.commit()

        return await self._operation_result(place_id, place, operation, status, collected, successful, cursor, fallback_used, error, stop_reason)

    async def _operation_result(
        self, place_id: str, place: Place, operation, status: str, collected: int, successful: int, cursor: str | None, fallback_used: bool, message: str | None, stop_reason: str | None
    ) -> ReviewSyncResponse:
        relevance_state = await self._collection_state(place, "qualityScore")
        stored = await self.reviews.list_for_place(
            place,
            sort=ReviewSort.RELEVANT if relevance_state and relevance_state.active_snapshot_id else ReviewSort.RECENT,
            relevance_snapshot_id=relevance_state.active_snapshot_id if relevance_state else None,
        )
        topics = await self.reviews.list_topics_for_place(place)
        return ReviewSyncResponse(
            place_id=place_id,
            status=status,
            collected_unique_count=collected,
            successful_request_count=successful,
            operation_id=operation.id,
            estimated_request_count=operation.requested_units,
            cached_response_count=operation.cached_response_count,
            failed_request_count=operation.failed_request_count,
            uncertain_request_count=operation.uncertain_request_count,
            released_reserved_count=operation.released_reserved_count,
            remaining_local_budget=await ProviderOperationRepository(self.session).remaining_local_budget(operation),
            pagination_cursor=cursor,
            stop_reason=stop_reason,
            reviews=[review_to_response(item) for item in stored],
            topics=[topic_to_response(item) for item in topics],
            topics_fetched_at=max((item.snapshot_fetched_at for item in topics), default=None),
            fallback_used=fallback_used,
            message=message,
        )

    async def _discard_unactivated_relevance_snapshot(self, place: Place, state: ReviewCollectionState | None, snapshot_id) -> None:
        await self.session.execute(delete(ReviewRelevanceRank).where(
            ReviewRelevanceRank.place_id == place.id,
            ReviewRelevanceRank.snapshot_id == snapshot_id,
        ))
        persisted_state = await self._collection_state(place, "qualityScore")
        if persisted_state is not None and persisted_state.pending_snapshot_id == snapshot_id:
            persisted_state.pending_snapshot_id = None
        await self.session.commit()

    async def _store_relevance_rank(self, place: Place, review: Review, snapshot_id, rank: int) -> None:
        existing = await self.session.scalar(select(ReviewRelevanceRank).where(
            ReviewRelevanceRank.place_id == place.id,
            ReviewRelevanceRank.snapshot_id == snapshot_id,
            ReviewRelevanceRank.review_id == review.id,
        ))
        if existing is None:
            self.session.add(ReviewRelevanceRank(
                place_id=place.id,
                review_id=review.id,
                provider=settings.review_provider,
                provider_sort="qualityScore",
                language_code=settings.serpapi_language or "en",
                snapshot_id=snapshot_id,
                rank=rank,
                fetched_at=utcnow(),
            ))
        else:
            existing.rank = rank
            existing.fetched_at = utcnow()
        await self.session.flush()

    async def _collection_state(self, place: Place, provider_sort: str = "qualityScore") -> ReviewCollectionState | None:
        return (await self.session.execute(select(ReviewCollectionState).where(
            ReviewCollectionState.place_id == place.id,
            ReviewCollectionState.provider == settings.review_provider,
            ReviewCollectionState.provider_sort == provider_sort,
        ))).scalar_one_or_none()

    async def _store_provider_cursor(self, place: Place, cursor: str | None, provider_sort: str = "qualityScore") -> ReviewCollectionState:
        state = await self._collection_state(place, provider_sort)
        if state is None:
            state = ReviewCollectionState(place_id=place.id, provider=settings.review_provider, provider_sort=provider_sort)
            self.session.add(state)
        state.pagination_cursor = cursor
        state.cursor_updated_at = utcnow()
        state.exhausted_at = utcnow() if cursor is None else None
        await self.session.flush()
        return state

    async def refresh(
        self, place_id: str, request: ReviewSyncRequest, idempotency_key: str | None = None
    ) -> ReviewSyncResponse | ProviderOperationResponse:
        return await self._sync(
            place_id,
            request.model_copy(update={"force": True}),
            is_refresh=True,
            idempotency_key=idempotency_key,
        )

    async def delete_reviews(self, place_id: str) -> int:
        place = await self._get_place(place_id)
        count = await self.reviews.delete_for_place(place)
        await self.session.commit()
        return count

    def _review_provider(self, name: str) -> ReviewProvider:
        if name == "serpapi":
            return SerpApiReviewProvider()
        if name == "google_places":
            return GooglePlacesReviewProvider()
        raise AppError("UNKNOWN_REVIEW_PROVIDER", f"Unknown review provider: {name}", 500)

    async def _try_place_lock(self, place_id: str) -> bool:
        result = await self.session.execute(
            text("select pg_try_advisory_lock(hashtext(:place_id))"), {"place_id": place_id}
        )
        return bool(result.scalar_one())

    async def _release_place_lock(self, place_id: str) -> None:
        await self.session.execute(
            text("select pg_advisory_unlock(hashtext(:place_id))"), {"place_id": place_id}
        )

    async def _get_place(self, place_id: str) -> Place:
        place = await self.places.get_by_google_place_id(place_id)
        if place is None:
            raise AppError("PLACE_NOT_FOUND", "Place is not stored. Select or persist it first.", 404)
        return place
