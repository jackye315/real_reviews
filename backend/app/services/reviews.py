from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.models.place import Place
from app.models.review import Review
from app.providers.base import ReviewProvider
from app.providers.google_places import GooglePlacesReviewProvider
from app.providers.serpapi import SerpApiReviewProvider
from app.repositories.places import PlaceRepository
from app.repositories.reviews import ReviewRepository
from app.repositories.usage import UsageRepository
from app.schemas.reviews import ReviewListResponse, ReviewResponse, ReviewSort, ReviewSyncRequest, ReviewSyncResponse, ReviewTopicResponse


def estimate_serpapi_requests(target_count: int) -> int:
    if target_count <= 8:
        return 1
    return 1 + ((target_count - 8 + 19) // 20)


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
        source_labels=labels,
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
        sort: ReviewSort = ReviewSort.RECENT,
    ) -> ReviewListResponse:
        place = await self._get_place(place_id)
        reviews = await self.reviews.list_for_place(place, rating=rating, sort=sort)
        total = await self.reviews.count_for_place(place)
        filtered_total = await self.reviews.count_for_place(place, rating=rating)
        topics = await self.reviews.list_topics_for_place(place)
        return ReviewListResponse(
            reviews=[review_to_response(item) for item in reviews],
            total=total,
            filtered_total=filtered_total,
            topics=[topic_to_response(item) for item in topics],
            topics_fetched_at=max((item.snapshot_fetched_at for item in topics), default=None),
        )

    async def sync(self, place_id: str, request: ReviewSyncRequest) -> ReviewSyncResponse:
        return await self._sync(place_id, request, is_refresh=False)

    async def _sync(
        self, place_id: str, request: ReviewSyncRequest, is_refresh: bool
    ) -> ReviewSyncResponse:
        place = await self._get_place(place_id)
        existing = await self.reviews.list_for_place(place)
        if existing and not request.force:
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
        estimated_requests = estimate_serpapi_requests(target)
        if estimated_requests > 1 and not request.confirm_cost:
            raise AppError(
                "COST_CONFIRMATION_REQUIRED",
                f"This may use approximately {estimated_requests} SerpApi searches. Set confirm_cost=true to continue.",
                409,
            )
        remaining = await self.usage.remaining_success_budget(
            "serpapi", settings.serpapi_monthly_request_budget
        )
        if remaining <= 0:
            raise AppError("SERPAPI_BUDGET_EXHAUSTED", "Local SerpApi budget is exhausted.", 429)

        lock_acquired = await self._try_place_lock(place.google_place_id)
        if not lock_acquired:
            raise AppError("SYNC_ALREADY_RUNNING", "A sync for this place is already running.", 409)

        run = await self.reviews.create_sync_run(place, settings.review_provider, target)
        await self.session.commit()
        provider = self._review_provider(settings.review_provider)
        fallback = self._review_provider(settings.review_fallback_provider)
        cursor: str | None = request.cursor
        collected = 0
        processed = 0
        successful = 0
        fallback_used = False
        status = "completed"
        error: str | None = None
        stop_reason: str | None = None
        known_streak = 0
        topic_field_observed = False
        topic_count_observed = 0
        known_streak_limit = (
            settings.refresh_known_streak_limit if is_refresh and request.cursor is None else 0
        )

        try:
            while processed < target and successful < remaining:
                page_size = min(20, target - processed)
                page_from_fallback = False
                try:
                    page = await provider.fetch_page(
                        place.google_place_id, cursor, page_size, settings.serpapi_review_sort
                    )
                except Exception as exc:
                    await self.usage.increment(settings.review_provider, failed=1)
                    if processed > 0:
                        await self.session.commit()
                        raise
                    page = await fallback.fetch_page(
                        place.google_place_id, None, min(5, page_size), settings.serpapi_review_sort
                    )
                    page_from_fallback = True
                    fallback_used = True
                    error = f"Primary review provider failed; used fallback: {type(exc).__name__}"

                if not page.reviews and processed == 0 and not page_from_fallback:
                    if page.cached:
                        await self.usage.increment(settings.review_provider, cached=1)
                    else:
                        await self.usage.increment(
                            settings.review_provider, successful=page.successful_request_count
                        )
                    successful += page.successful_request_count
                    page = await fallback.fetch_page(
                        place.google_place_id, None, min(5, page_size), settings.serpapi_review_sort
                    )
                    page_from_fallback = True
                    fallback_used = True
                    error = "Primary review provider returned no reviews; used fallback."

                usage_provider = settings.review_fallback_provider if page_from_fallback else settings.review_provider
                if page.topics is not None and not page_from_fallback:
                    topic_field_observed = True
                    topic_count_observed = len(page.topics)
                    await self.reviews.upsert_topic_snapshot(
                        place, usage_provider, page.topics, settings.serpapi_language or None
                    )
                if page.cached:
                    await self.usage.increment(usage_provider, cached=1)
                else:
                    await self.usage.increment(usage_provider, successful=page.successful_request_count)
                successful += page.successful_request_count
                if not page.reviews:
                    break
                for item in page.reviews:
                    _, outcome = await self.reviews.upsert_normalized(place, item)
                    processed += 1
                    if outcome == "created":
                        collected += 1
                    if outcome == "unchanged":
                        known_streak += 1
                    else:
                        known_streak = 0
                cursor = page.next_cursor
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
                if should_stop_after_page:
                    break
            if processed < target and cursor:
                status = "partial"
            elif processed >= target and cursor:
                stop_reason = stop_reason or "target_reached"
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
            await self.session.commit()
        except Exception as exc:
            await self.session.rollback()
            await self.reviews.complete_sync_run(
                run, "failed", collected, successful, cursor, type(exc).__name__, "error"
            )
            await self.session.commit()
            raise
        finally:
            await self._release_place_lock(place.google_place_id)

        stored = await self.reviews.list_for_place(place)
        topics = await self.reviews.list_topics_for_place(place)
        return ReviewSyncResponse(
            place_id=place_id,
            status=status,
            collected_unique_count=collected,
            successful_request_count=successful,
            pagination_cursor=cursor,
            stop_reason=stop_reason,
            reviews=[review_to_response(item) for item in stored],
            topics=[topic_to_response(item) for item in topics],
            topics_fetched_at=max((item.snapshot_fetched_at for item in topics), default=None),
            fallback_used=fallback_used,
            message=error,
        )

    async def refresh(self, place_id: str, request: ReviewSyncRequest) -> ReviewSyncResponse:
        return await self._sync(
            place_id, request.model_copy(update={"force": True}), is_refresh=True
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
