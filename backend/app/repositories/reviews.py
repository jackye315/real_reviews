from __future__ import annotations

from datetime import datetime
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utcnow
from app.models.place import Place
from app.models.review import Review
from app.models.review_origin import ReviewOrigin
from app.models.review_sync_run import ReviewSyncRun
from app.models.review_topic import ReviewTopic
from app.providers.base import NormalizedReview, NormalizedReviewOrigin, NormalizedReviewTopic
from app.schemas.reviews import ReviewSort
from app.utils.text import normalize_author_name, stable_text_hash


REVIEW_SORTS = {
    ReviewSort.RECENT: (
        Review.publication_timestamp.desc().nullslast(),
        Review.id.asc(),
    ),
    ReviewSort.OLDEST: (
        Review.publication_timestamp.asc().nullslast(),
        Review.id.asc(),
    ),
    ReviewSort.RATING_HIGH: (
        Review.rating.desc().nullslast(),
        Review.publication_timestamp.desc().nullslast(),
        Review.id.asc(),
    ),
    ReviewSort.RATING_LOW: (
        Review.rating.asc().nullslast(),
        Review.publication_timestamp.desc().nullslast(),
        Review.id.asc(),
    ),
}


class ReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_for_place(self, place: Place, rating: int | None = None) -> int:
        statement = select(func.count()).select_from(Review).where(Review.place_id == place.id)
        if rating is not None:
            statement = statement.where(Review.rating == rating)
        result = await self.session.execute(statement)
        return int(result.scalar_one())

    async def list_for_place(
        self,
        place: Place,
        rating: int | None = None,
        sort: ReviewSort = ReviewSort.RECENT,
    ) -> list[Review]:
        statement = select(Review).options(selectinload(Review.origins)).where(Review.place_id == place.id)
        if rating is not None:
            statement = statement.where(Review.rating == rating)
        result = await self.session.execute(statement.order_by(*REVIEW_SORTS[sort]))
        return list(result.scalars().unique())

    async def list_for_place_by_ids(
        self,
        place: Place,
        review_ids: set,
        sort: ReviewSort = ReviewSort.RECENT,
    ) -> list[Review]:
        if not review_ids:
            return []
        result = await self.session.execute(
            select(Review)
            .options(selectinload(Review.origins))
            .where(Review.place_id == place.id, Review.id.in_(review_ids))
            .order_by(*REVIEW_SORTS[sort])
        )
        return list(result.scalars().unique())

    async def find_by_origin(self, provider_name: str, provider_review_id: str | None) -> Review | None:
        if not provider_review_id:
            return None
        result = await self.session.execute(
            select(Review)
            .join(ReviewOrigin)
            .options(selectinload(Review.origins))
            .where(
                ReviewOrigin.provider_name == provider_name,
                ReviewOrigin.provider_review_id == provider_review_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_external_review_id(self, provider_review_id: str | None) -> Review | None:
        if not provider_review_id:
            return None
        result = await self.session.execute(
            select(Review)
            .join(ReviewOrigin)
            .options(selectinload(Review.origins))
            .where(ReviewOrigin.provider_review_id == provider_review_id)
        )
        return result.scalar_one_or_none()

    async def find_by_composite(self, place: Place, item: NormalizedReview, content_hash: str) -> Review | None:
        origin = item.origin
        if origin and origin.contributor_id:
            result = await self.session.execute(
                select(Review)
                .join(ReviewOrigin)
                .options(selectinload(Review.origins))
                .where(
                    Review.place_id == place.id,
                    ReviewOrigin.contributor_id == origin.contributor_id,
                    Review.rating == item.rating,
                    Review.publication_timestamp == item.publication_timestamp,
                    Review.normalized_content_hash == content_hash,
                )
            )
            match = result.scalar_one_or_none()
            if match:
                return match
        result = await self.session.execute(
            select(Review)
            .options(selectinload(Review.origins))
            .where(
                Review.place_id == place.id,
                Review.rating == item.rating,
                Review.publication_timestamp == item.publication_timestamp,
                Review.normalized_content_hash == content_hash,
            )
        )
        matches = list(result.scalars().unique())
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            normalized_author = normalize_author_name(item.author_display_name)
            for match in matches:
                if normalize_author_name(match.author_display_name) == normalized_author:
                    return match
        return None

    async def upsert_normalized(self, place: Place, item: NormalizedReview) -> tuple[Review, str]:
        content_hash = stable_text_hash(item.text or item.original_text)
        origin = item.origin
        review = None
        if origin:
            review = await self.find_by_origin(origin.provider_name, origin.provider_review_id)
        if review is None and origin:
            review = await self.find_by_external_review_id(origin.provider_review_id)
        if review is None:
            review = await self.find_by_composite(place, item, content_hash)
        created = review is None
        outcome = "created"
        if review is None:
            review = Review(place_id=place.id, normalized_content_hash=content_hash)
            self.session.add(review)
            review.first_fetched_at = utcnow()
        else:
            outcome = "changed" if self._has_material_changes(review, item, content_hash) else "unchanged"
        existing_origin_names = {existing.provider_name for existing in getattr(review, "origins", [])}
        incoming_is_google = origin is not None and origin.provider_name == "google_places"
        has_google_origin = "google_places" in existing_origin_names
        prefer_incoming = created or incoming_is_google or not has_google_origin
        if prefer_incoming or review.rating is None:
            review.rating = item.rating
        if prefer_incoming or not review.text:
            review.text = item.text
        if prefer_incoming or not review.original_text:
            review.original_text = item.original_text
        if prefer_incoming or not review.author_display_name:
            review.author_display_name = item.author_display_name
        if prefer_incoming or not review.author_avatar_url:
            review.author_avatar_url = item.author_avatar_url
        if prefer_incoming or review.publication_timestamp is None:
            review.publication_timestamp = item.publication_timestamp
        if prefer_incoming or review.last_edit_timestamp is None:
            review.last_edit_timestamp = item.last_edit_timestamp
        if prefer_incoming or not review.canonical_source_url:
            review.canonical_source_url = item.canonical_source_url
        review.last_seen_at = utcnow()
        await self.session.flush()
        if origin:
            await self._attach_origin(review, origin)
        await self.session.flush()
        return review, outcome

    def _has_material_changes(
        self, review: Review, item: NormalizedReview, content_hash: str
    ) -> bool:
        canonical_changed = any(
            [
                review.normalized_content_hash != content_hash,
                review.rating != item.rating,
                review.text != item.text,
                review.original_text != item.original_text,
                review.publication_timestamp != item.publication_timestamp,
                review.last_edit_timestamp != item.last_edit_timestamp,
                review.canonical_source_url != item.canonical_source_url,
                review.author_display_name != item.author_display_name,
                review.author_avatar_url != item.author_avatar_url,
            ]
        )
        if canonical_changed:
            return True
        if item.origin is None:
            return False
        matching_origin = self._matching_origin(review, item.origin)
        if matching_origin is None:
            return True
        return any(
            [
                matching_origin.provider_place_id != item.origin.provider_place_id,
                matching_origin.source_label != item.origin.source_label,
                matching_origin.source_url != item.origin.source_url,
                matching_origin.contributor_id != item.origin.contributor_id,
                matching_origin.author_profile_url != item.origin.author_profile_url,
                matching_origin.author_avatar_url != item.origin.author_avatar_url,
                matching_origin.provider_publication_timestamp
                != item.origin.provider_publication_timestamp,
                matching_origin.provider_edit_timestamp != item.origin.provider_edit_timestamp,
            ]
        )

    @staticmethod
    def _matching_origin(
        review: Review, origin: NormalizedReviewOrigin
    ) -> ReviewOrigin | None:
        for existing in getattr(review, "origins", []) or []:
            if (
                existing.provider_name == origin.provider_name
                and existing.provider_review_id == origin.provider_review_id
            ):
                return existing
        return None

    async def _attach_origin(self, review: Review, origin) -> None:
        existing = None
        if origin.provider_review_id:
            result = await self.session.execute(
                select(ReviewOrigin).where(
                    ReviewOrigin.provider_name == origin.provider_name,
                    ReviewOrigin.provider_review_id == origin.provider_review_id,
                )
            )
            existing = result.scalar_one_or_none()
        if existing is None:
            existing = ReviewOrigin(review_id=review.id, provider_name=origin.provider_name)
            self.session.add(existing)
        existing.review_id = review.id
        existing.provider_review_id = origin.provider_review_id
        existing.provider_place_id = origin.provider_place_id
        existing.source_label = origin.source_label
        existing.source_url = origin.source_url
        existing.contributor_id = origin.contributor_id
        existing.author_profile_url = origin.author_profile_url
        existing.author_avatar_url = origin.author_avatar_url
        existing.provider_publication_timestamp = origin.provider_publication_timestamp
        existing.provider_edit_timestamp = origin.provider_edit_timestamp
        existing.fetched_at = utcnow()

    async def list_topics_for_place(self, place: Place, provider_name: str = "serpapi") -> list[ReviewTopic]:
        result = await self.session.execute(
            select(ReviewTopic)
            .where(
                ReviewTopic.place_id == place.id,
                ReviewTopic.provider_name == provider_name,
                ReviewTopic.active.is_(True),
            )
            .order_by(ReviewTopic.rank.asc(), ReviewTopic.keyword.asc())
        )
        return list(result.scalars())

    async def upsert_topic_snapshot(
        self,
        place: Place,
        provider_name: str,
        topics: list[NormalizedReviewTopic],
        language_code: str | None,
    ) -> None:
        now = utcnow()
        incoming_ids = {topic.provider_topic_id for topic in topics}
        deactivation_filter = (
            ReviewTopic.place_id == place.id,
            ReviewTopic.provider_name == provider_name,
            ReviewTopic.language_code == language_code,
            ReviewTopic.active.is_(True),
        )
        if incoming_ids:
            await self.session.execute(
                update(ReviewTopic)
                .where(*deactivation_filter, ~ReviewTopic.provider_topic_id.in_(incoming_ids))
                .values(active=False, last_seen_at=now, snapshot_fetched_at=now)
            )
        else:
            await self.session.execute(
                update(ReviewTopic)
                .where(*deactivation_filter)
                .values(active=False, last_seen_at=now, snapshot_fetched_at=now)
            )
        for topic in topics:
            result = await self.session.execute(
                select(ReviewTopic).where(
                    ReviewTopic.place_id == place.id,
                    ReviewTopic.provider_name == provider_name,
                    ReviewTopic.provider_topic_id == topic.provider_topic_id,
                    ReviewTopic.language_code == topic.language_code,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                existing = ReviewTopic(
                    place_id=place.id,
                    provider_name=provider_name,
                    provider_topic_id=topic.provider_topic_id,
                    language_code=topic.language_code,
                    first_seen_at=now,
                )
                self.session.add(existing)
            existing.keyword = topic.keyword
            existing.mentions = topic.mentions
            existing.rank = topic.rank
            existing.active = True
            existing.last_seen_at = now
            existing.snapshot_fetched_at = now
        await self.session.flush()

    async def delete_for_place(self, place: Place) -> int:
        await self.session.execute(delete(ReviewTopic).where(ReviewTopic.place_id == place.id))
        result = await self.session.execute(delete(Review).where(Review.place_id == place.id))
        return int(result.rowcount or 0)

    async def create_sync_run(self, place: Place, provider: str, target_count: int) -> ReviewSyncRun:
        run = ReviewSyncRun(place_id=place.id, provider=provider, requested_target_count=target_count)
        self.session.add(run)
        await self.session.flush()
        return run

    async def complete_sync_run(
        self,
        run: ReviewSyncRun,
        status: str,
        collected: int,
        successful: int,
        cursor: str | None,
        error: str | None = None,
        stop_reason: str | None = None,
        topic_field_observed: bool | None = None,
        topic_count_observed: int | None = None,
    ) -> ReviewSyncRun:
        run.status = status
        run.collected_unique_count = collected
        run.successful_request_count = successful
        run.pagination_cursor = cursor
        run.error_summary = error
        run.stop_reason = stop_reason
        if topic_field_observed is not None:
            run.topic_field_observed = topic_field_observed
        if topic_count_observed is not None:
            run.topic_count_observed = topic_count_observed
        run.completed_at = datetime.now(tz=utcnow().tzinfo)
        await self.session.flush()
        return run
