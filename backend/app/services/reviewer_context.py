from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from statistics import median, variance
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import AppError
from app.db.base import utcnow
from app.models.place import Place
from app.models.place_data_id import PlaceDataId
from app.models.review_origin import ReviewOrigin
from app.models.provider_operation import ProviderOperation
from app.models.review import Review
from app.models.reviewer import Reviewer
from app.providers.serpapi_contributor import SerpApiContributorReviewProvider
from app.repositories.provider_operations import ProviderOperationRepository
from app.repositories.usage import UsageRepository
from app.schemas.operations import ProviderOperationResponse
from app.schemas.reviewers import (
    MatchLevel,
    ReviewerComparisonResponse,
    ReviewerContextDeleteResponse,
    ReviewerContextResponse,
    ReviewerCurrentReviewResponse,
    ReviewerRelevantReviewResponse,
    ReviewerResponse,
    TimeWindow,
)
from app.services.provider_operations import ProviderOperationService, account_snapshot, serpapi_semaphore
from app.services.reviews import review_to_response
from app.utils.contributor_dates import parse_contributor_date
from app.utils.text import stable_text_hash
from app.utils.venue_types import CLASSIFIER_VERSION, classify_current_place_types, classify_food_drink_decision

_ACTIVE = ("reserved", "running")


class SnapshotStats:
    def __init__(self) -> None:
        self.accepted = 0
        self.rejected_non_food = 0
        self.rejected_unknown = 0
        self.rejected_missing = 0
        self.duplicate = 0
        self.new = 0
        self.updated = 0
        self.unchanged = 0

    def metadata(self, generation: int, returned: int) -> dict[str, int]:
        return {
            "provider_results_returned": returned,
            "accepted_food_and_drink_count": self.accepted,
            "rejected_non_food_count": self.rejected_non_food,
            "rejected_unknown_type_count": self.rejected_unknown,
            "rejected_missing_required_data_count": self.rejected_missing,
            "duplicate_result_count": self.duplicate,
            "context_generation": generation,
            "new_canonical_review_count": self.new,
            "updated_existing_review_count": self.updated,
            "unchanged_review_count": self.unchanged,
        }


class ReviewerContextService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _enabled(self) -> None:
        if not settings.reviewer_context_enabled:
            raise AppError("FEATURE_DISABLED", "Reviewer context is not enabled.", 403)

    async def profile(self, reviewer_id: UUID, current_review_id: UUID) -> ReviewerContextResponse:
        self._enabled()
        reviewer, current = await self._reviewer_and_current(reviewer_id, current_review_id)
        comparison = await self.comparison(reviewer_id, current_review_id, "two_years", "exact_type", _validated=(reviewer, current)) if reviewer.context_generation else None
        broader = None
        if comparison and comparison.sample_size < 5:
            broader = await self.comparison(reviewer_id, current_review_id, "two_years", "comparison_family", _validated=(reviewer, current))
        active = await self.session.execute(
            select(ProviderOperation.id).where(
                ProviderOperation.reviewer_id == reviewer.id,
                ProviderOperation.status.in_(_ACTIVE),
            ).order_by(ProviderOperation.created_at.desc()).limit(1)
        )
        active_id = active.scalar_one_or_none()
        stale = bool(
            reviewer.context_fetched_at
            and utcnow() - reviewer.context_fetched_at > timedelta(days=settings.reviewer_context_stale_after_days)
        )
        return ReviewerContextResponse(
            reviewer=self._reviewer_response(reviewer),
            current=ReviewerCurrentReviewResponse(
                review=review_to_response(current),
                restaurant_name=current.place.display_name,
                restaurant_place_id=current.place.google_place_id,
                normalized_venue_type=self._current_type(current.place).normalized if self._current_type(current.place) else None,
                comparison_family=self._current_type(current.place).family if self._current_type(current.place) else None,
            ),
            comparison=comparison,
            broader_comparison=broader,
            active_operation_id=active_id,
            stale=stale,
        )

    async def comparison(
        self,
        reviewer_id: UUID,
        current_review_id: UUID,
        time_window: TimeWindow,
        match_level: MatchLevel,
        _validated: tuple[Reviewer, Review] | None = None,
    ) -> ReviewerComparisonResponse:
        self._enabled()
        reviewer, current = _validated or await self._reviewer_and_current(reviewer_id, current_review_id)
        current_type = self._current_type(current.place)
        if current.rating is None:
            raise AppError("REVIEWER_REVIEW_MISMATCH", "Current review has no valid rating.", 400)
        if current_type is None or reviewer.context_generation == 0:
            return self._empty_comparison(current.rating, match_level, time_window, reviewer, current_type)
        type_column = Place.normalized_venue_type if match_level == "exact_type" else Place.comparison_family
        type_value = current_type.normalized if match_level == "exact_type" else current_type.family
        statement = (
            select(Review, Place)
            .join(Place)
            .where(
                Review.reviewer_id == reviewer.id,
                Review.contributor_generation == reviewer.context_generation,
                Review.place_id != current.place_id,
                Review.rating.between(1, 5),
                type_column == type_value,
            )
        )
        rows = list((await self.session.execute(statement.order_by(
            func.coalesce(Review.publication_timestamp, Review.publication_date_lower_bound).desc().nulls_last(),
            Review.id.asc(),
        ))).all())
        rows = [(review, place) for review, place in rows if _within_time_window(review, time_window)]
        values = [review.rating for review, _place in rows if review.rating is not None]
        distribution = {str(value): values.count(value) for value in range(1, 6)}
        average = sum(values) / len(values) if values else None
        sample_variance = variance(values) if len(values) >= 2 else None
        standard_deviation = sample_variance ** 0.5 if sample_variance is not None else None
        return ReviewerComparisonResponse(
            current_rating=current.rating,
            match_level=match_level,
            normalized_venue_type=current_type.normalized,
            comparison_family=current_type.family,
            time_window=time_window,
            sample_size=len(values),
            average_rating=average,
            median_rating=float(median(values)) if values else None,
            sample_variance=sample_variance,
            standard_deviation=standard_deviation,
            difference_from_average=current.rating - average if average is not None else None,
            rating_distribution=distribution,
            individual_ratings=values if len(values) <= 2 else [],
            contains_approximate_dates=any(review.publication_date_is_approximate for review, _place in rows),
            snapshot_fetched_at=reviewer.context_fetched_at,
            context_generation=reviewer.context_generation,
            relevant_reviews=[
                ReviewerRelevantReviewResponse(
                    id=review.id,
                    place_name=place.display_name,
                    rating=review.rating,
                    text=review.text,
                    original_text=review.original_text,
                    provider_date_text=review.provider_date_text,
                    publication_date_is_approximate=review.publication_date_is_approximate,
                    source_url=review.canonical_source_url,
                )
                for review, place in rows
                if review.rating is not None
            ],
        )

    async def start_context(
        self, reviewer_id: UUID, current_review_id: UUID, confirm_cost: bool, force_refresh: bool, idempotency_key: str | None
    ) -> ReviewerContextResponse | ProviderOperationResponse:
        self._enabled()
        reviewer, _ = await self._reviewer_and_current(reviewer_id, current_review_id)
        if not reviewer.google_contributor_id:
            raise AppError("REVIEWER_CONTRIBUTOR_ID_UNAVAILABLE", "No public contributor ID is available for this reviewer.", 409)
        operations = ProviderOperationRepository(self.session)
        if idempotency_key:
            replay = await operations.find_by_idempotency("serpapi", idempotency_key)
            if replay is not None:
                return await ProviderOperationService(self.session).view(replay)
        if reviewer.context_generation and not force_refresh:
            return await self.profile(reviewer_id, current_review_id)
        if not confirm_cost:
            raise AppError("COST_CONFIRMATION_REQUIRED", "This will contact SerpApi and may use approximately 1 search. Set confirm_cost=true to continue.", 409)
        if not idempotency_key:
            raise AppError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key is required for reviewer context.", 400)
        fingerprint = hashlib.sha256(json.dumps({"reviewer_id": str(reviewer_id), "review": str(current_review_id), "force": force_refresh}, sort_keys=True).encode()).hexdigest()
        operation, _ = await operations.reserve(
            provider="serpapi", operation_type="serpapi_contributor_reviews", place_id=None,
            reviewer_id=reviewer.id, idempotency_key=idempotency_key, request_fingerprint=fingerprint,
            requested_units=1, snapshot=await account_snapshot(),
        )
        asyncio.create_task(self._run_context(reviewer.id, current_review_id, operation.id), name=f"reviewer-context-{operation.id}")
        return await ProviderOperationService(self.session).view(operation)

    @staticmethod
    async def _run_context(reviewer_id: UUID, current_review_id: UUID, operation_id: UUID) -> None:
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            operations = ProviderOperationRepository(session)
            operation = await operations.get(operation_id)
            reviewer = await session.get(Reviewer, reviewer_id)
            if operation is None or reviewer is None:
                return
            try:
                await operations.mark_running(operation)
                if await operations.cancellation_requested(operation.id):
                    await operations.finish(operation, status="cancelled", stop_reason="user_cancelled")
                    return
                async with serpapi_semaphore():
                    snapshot = await SerpApiContributorReviewProvider().fetch(reviewer.google_contributor_id or "")
                if await operations.cancellation_requested(operation.id):
                    await operations.settle_page(operation, uncertain=1)
                    await operations.finish(operation, status="cancelled", stop_reason="user_cancelled")
                    return
                stats = await ReviewerContextService(session)._persist_snapshot(reviewer, snapshot)
                await UsageRepository(session).increment("serpapi", successful=0 if snapshot.cached else 1, cached=1 if snapshot.cached else 0, operation_type="serpapi_contributor_reviews")
                await operations.settle_page(operation, successful=0 if snapshot.cached else 1, cached=1 if snapshot.cached else 0, collected=stats.new)
                await session.commit()
                context = await ReviewerContextService(session).profile(reviewer_id, current_review_id)
                operation.result_metadata = {**stats.metadata(reviewer.context_generation, len(snapshot.reviews)), "reviewer_context": context.model_dump(mode="json")}
                await session.commit()
                await operations.finish(operation, status="completed")
            except Exception as exc:
                await session.rollback()
                operation = await operations.get(operation_id)
                if operation:
                    operation.result_metadata = {"error_code": "REVIEWER_CONTEXT_PROVIDER_FAILED"}
                    await session.commit()
                    await operations.finish(operation, status="failed", stop_reason="error", error_summary=type(exc).__name__)

    async def _persist_snapshot(self, reviewer: Reviewer, snapshot) -> SnapshotStats:
        now = utcnow()
        accepted = []
        stats = SnapshotStats()
        seen_review_ids: set[str] = set()
        for candidate in snapshot.reviews:
            if not candidate.review_id or candidate.rating is None or not 1 <= candidate.rating <= 5 or not candidate.data_id:
                stats.rejected_missing += 1
                continue
            if candidate.review_id in seen_review_ids:
                stats.duplicate += 1
                continue
            seen_review_ids.add(candidate.review_id)
            decision = classify_food_drink_decision(candidate.place_type)
            if decision.venue_type is None:
                if decision.decision == "rejected_explicit_non_food":
                    stats.rejected_non_food += 1
                else:
                    stats.rejected_unknown += 1
                continue
            accepted.append((candidate, decision.venue_type))
        stats.accepted = len(accepted)
        reviewer.context_generation += 1
        generation = reviewer.context_generation
        for candidate, classification in accepted:
            review = (await self.session.execute(select(Review).where(Review.google_review_id == candidate.review_id))).scalar_one_or_none()
            mapping = await self.session.get(PlaceDataId, candidate.data_id)
            if review is not None:
                place = await self.session.get(Place, review.place_id)
                if mapping is None:
                    mapping = PlaceDataId(data_id=candidate.data_id, place_id=place.id)
                    self.session.add(mapping)
            elif mapping is not None:
                place = await self.session.get(Place, mapping.place_id)
            else:
                place = Place(display_name=candidate.place_title or "Observed venue", state="observed")
                self.session.add(place)
                await self.session.flush()
                mapping = PlaceDataId(data_id=candidate.data_id, place_id=place.id)
                self.session.add(mapping)
            place.provider_type = candidate.place_type
            place.normalized_venue_type = classification.normalized
            place.comparison_family = classification.family
            place.type_source = "serpapi_contributor"
            place.type_confidence = "high"
            place.classifier_version = CLASSIFIER_VERSION
            created = review is None
            changed = False
            if review is None:
                review = Review(place_id=place.id, normalized_content_hash=stable_text_hash(candidate.text), google_review_id=candidate.review_id)
                self.session.add(review)
                await self.session.flush()
                self.session.add(ReviewOrigin(review_id=review.id, provider_name="serpapi", provider_review_id=candidate.review_id, provider_place_id=None, source_label="Google", source_url=candidate.source_url))
            changed = created or any((
                review.reviewer_id != reviewer.id,
                review.rating != candidate.rating,
                bool(candidate.text and candidate.text != review.text),
                bool(candidate.source_url and candidate.source_url != review.canonical_source_url),
                review.observed_data_id != candidate.data_id,
            ))
            review.reviewer_id = reviewer.id
            review.rating = candidate.rating
            review.text = candidate.text or review.text
            review.canonical_source_url = candidate.source_url or review.canonical_source_url
            review.observed_data_id = candidate.data_id
            review.seen_via_contributor_at = now
            review.contributor_generation = generation
            review.provider_date_text = candidate.date_text
            parsed_date = parse_contributor_date(candidate.date_text, now)
            review.publication_date_lower_bound = parsed_date.lower
            review.publication_date_upper_bound = parsed_date.upper
            review.publication_date_precision = parsed_date.precision
            review.publication_date_is_approximate = parsed_date.approximate
            review.publication_date_basis = parsed_date.basis
            if created:
                stats.new += 1
            elif changed:
                stats.updated += 1
            else:
                stats.unchanged += 1
        profile = snapshot.profile
        reviewer.contributor_profile = {
            "display_name": profile.get("name"), "avatar_url": profile.get("thumbnail"), "profile_url": profile.get("link"),
            "level": profile.get("level"), "points": profile.get("points"), "provider_rating_count": profile.get("ratings"),
            "provider_review_count": profile.get("reviews"), "provider_photo_count": profile.get("photos"),
        }
        reviewer.context_fetched_at = now
        reviewer.context_status = "available"
        reviewer.provider_results_returned = len(snapshot.reviews)
        reviewer.accepted_food_and_drink_count = stats.accepted
        reviewer.rejected_non_food_count = stats.rejected_non_food
        reviewer.rejected_unknown_type_count = stats.rejected_unknown
        reviewer.rejected_missing_required_data_count = stats.rejected_missing
        await self.session.flush()
        return stats

    async def delete_context(self, reviewer_id: UUID) -> ReviewerContextDeleteResponse:
        # Local deletion remains available even when the feature is disabled in production.
        reviewer = await self.session.get(Reviewer, reviewer_id)
        if reviewer is None:
            raise AppError("REVIEWER_NOT_FOUND", "Reviewer was not found.", 404)
        contributor_rows = list((await self.session.execute(
            select(Review).where(Review.reviewer_id == reviewer.id, Review.contributor_generation.is_not(None))
        )).scalars())
        contributor_only = [row for row in contributor_rows if row.seen_via_restaurant_at is None]
        confirmed = [row for row in contributor_rows if row.seen_via_restaurant_at is not None]
        place_ids = {row.place_id for row in contributor_only}
        for row in contributor_only:
            await self.session.delete(row)
        for row in confirmed:
            row.contributor_generation = None
            row.seen_via_contributor_at = None
        await self.session.flush()
        removed_places = 0
        for place_id in place_ids:
            remaining = await self.session.scalar(select(func.count()).select_from(Review).where(Review.place_id == place_id))
            if not remaining:
                place = await self.session.get(Place, place_id)
                if place and place.state == "observed":
                    await self.session.delete(place)
                    removed_places += 1
        reviewer.contributor_profile = None
        reviewer.context_generation = 0
        reviewer.context_fetched_at = None
        reviewer.context_status = "not_loaded"
        reviewer.provider_results_returned = None
        reviewer.accepted_food_and_drink_count = None
        reviewer.rejected_non_food_count = None
        reviewer.rejected_unknown_type_count = None
        reviewer.rejected_missing_required_data_count = None
        await self.session.commit()
        return ReviewerContextDeleteResponse(
            contributor_only_reviews_removed=len(contributor_only),
            observed_places_removed=removed_places,
            restaurant_confirmed_reviews_preserved=len(confirmed),
        )

    async def _reviewer_and_current(self, reviewer_id: UUID, current_review_id: UUID) -> tuple[Reviewer, Review]:
        reviewer = await self.session.get(Reviewer, reviewer_id)
        if reviewer is None:
            raise AppError("REVIEWER_NOT_FOUND", "Reviewer was not found.", 404)
        current = (
            await self.session.execute(
                select(Review)
                .options(selectinload(Review.origins), selectinload(Review.images), selectinload(Review.place))
                .where(Review.id == current_review_id)
            )
        ).scalar_one_or_none()
        if current is None or current.reviewer_id != reviewer.id or current.place is None:
            raise AppError("REVIEWER_REVIEW_MISMATCH", "Review does not belong to this reviewer.", 400)
        return reviewer, current

    @staticmethod
    def _current_type(place: Place):
        if place.normalized_venue_type and place.comparison_family:
            from app.utils.venue_types import VenueType
            return VenueType(place.normalized_venue_type, place.comparison_family)
        return classify_current_place_types(place.place_types)

    @staticmethod
    def _reviewer_response(reviewer: Reviewer) -> ReviewerResponse:
        profile = reviewer.contributor_profile or {}
        return ReviewerResponse(
            id=reviewer.id,
            display_name=profile.get("display_name") or reviewer.display_name,
            avatar_url=profile.get("avatar_url") or reviewer.avatar_url,
            profile_url=profile.get("profile_url") or reviewer.profile_url,
            local_guide=reviewer.local_guide,
            provider_review_count=profile.get("provider_review_count") or reviewer.provider_review_count,
            provider_photo_count=profile.get("provider_photo_count") or reviewer.provider_photo_count,
            level=profile.get("level"),
            points=profile.get("points"),
            provider_rating_count=profile.get("provider_rating_count"),
            context_status=reviewer.context_status,
            context_fetched_at=reviewer.context_fetched_at,
            context_generation=reviewer.context_generation,
            provider_results_returned=reviewer.provider_results_returned,
            accepted_food_and_drink_count=reviewer.accepted_food_and_drink_count,
            rejected_non_food_count=reviewer.rejected_non_food_count,
            rejected_unknown_type_count=reviewer.rejected_unknown_type_count,
            rejected_missing_required_data_count=reviewer.rejected_missing_required_data_count,
        )

    @staticmethod
    def _empty_comparison(current_rating: int, match_level: MatchLevel, time_window: TimeWindow, reviewer: Reviewer, current_type) -> ReviewerComparisonResponse:
        return ReviewerComparisonResponse(
            current_rating=current_rating,
            match_level=match_level,
            normalized_venue_type=current_type.normalized if current_type else None,
            comparison_family=current_type.family if current_type else None,
            time_window=time_window,
            sample_size=0,
            rating_distribution={str(value): 0 for value in range(1, 6)},
            snapshot_fetched_at=reviewer.context_fetched_at,
            context_generation=reviewer.context_generation,
        )


def _within_time_window(review: Review, window: TimeWindow) -> bool:
    if window == "all_observed":
        return True
    if review.provider_date_text:
        text = review.provider_date_text.removeprefix("Edited ").strip().lower()
        match = re.fullmatch(r"(?:(a|an)|([0-9]+))\s+(day|week|month|year)s?\s+ago", text)
        if match:
            count = 1 if match.group(1) else int(match.group(2))
            unit = match.group(3)
            if unit in {"day", "week"}:
                return True
            if unit == "month":
                return count <= {"six_months": 5, "one_year": 11, "two_years": 23}[window]
            return count <= (1 if window == "two_years" else 0)
        return False
    cutoff = _cutoff(window)
    timestamp = review.publication_timestamp or review.publication_date_lower_bound
    return bool(cutoff and timestamp and timestamp > cutoff)


def _cutoff(window: TimeWindow) -> datetime | None:
    now = datetime.now(timezone.utc)
    if window == "six_months":
        return now - timedelta(days=183)
    if window == "one_year":
        return now - timedelta(days=365)
    if window == "two_years":
        return now - timedelta(days=730)
    return None
