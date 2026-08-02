from __future__ import annotations

from datetime import datetime
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.db.base import utcnow
from app.models.place import Place
from app.models.review import Review
from app.models.review_image import ReviewImage
from app.models.review_origin import ReviewOrigin
from app.models.review_sync_run import ReviewSyncRun
from app.models.review_relevance_rank import ReviewRelevanceRank
from app.models.review_topic import ReviewTopic
from app.providers.base import NormalizedReview, NormalizedReviewOrigin, NormalizedReviewTopic
from app.utils.review_rich_data import RichSection
from app.repositories.reviewers import ReviewerRepository
from app.schemas.reviews import ReviewSort
from app.utils.review_cursors import cursor_timestamp
from app.utils.text import normalize_author_name, stable_text_hash


REVIEW_SORTS = {
    ReviewSort.RELEVANT: (Review.publication_timestamp.desc().nullslast(), Review.id.asc()),
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
    def _ordered_statement(self, place: Place, rating: int | None, sort: ReviewSort, relevance_snapshot_id):
        statement = select(Review).options(selectinload(Review.origins), selectinload(Review.images)).where(Review.place_id == place.id)
        rank = None
        ordering = REVIEW_SORTS[sort]
        if sort == ReviewSort.RELEVANT:
            rank = aliased(ReviewRelevanceRank)
            statement = statement.outerjoin(
                rank,
                and_(
                    rank.review_id == Review.id,
                    rank.place_id == place.id,
                    rank.snapshot_id == relevance_snapshot_id,
                ),
            )
            ordering = (rank.rank.asc().nullslast(), Review.publication_timestamp.desc().nullslast(), Review.id.asc())
        if rating is not None:
            statement = statement.where(Review.rating == rating)
        return statement, ordering, rank

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def relevance_rank_for_review(self, place: Place, snapshot_id, review_id) -> int | None:
        if snapshot_id is None:
            return None
        return await self.session.scalar(select(ReviewRelevanceRank.rank).where(
            ReviewRelevanceRank.place_id == place.id,
            ReviewRelevanceRank.snapshot_id == snapshot_id,
            ReviewRelevanceRank.review_id == review_id,
        ))

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
        relevance_snapshot_id=None,
    ) -> list[Review]:
        statement, ordering, _rank = self._ordered_statement(place, rating, sort, relevance_snapshot_id)
        result = await self.session.execute(statement.order_by(*ordering))
        return list(result.scalars().unique())

    async def list_page_for_place(self, place: Place, rating: int | None, sort: ReviewSort, page_size: int, cursor: dict | None, relevance_snapshot_id=None) -> list[Review]:
        statement, ordering, rank = self._ordered_statement(place, rating, sort, relevance_snapshot_id)
        if cursor:
            statement = statement.where(self._after_cursor(sort, cursor, rank))
        result = await self.session.execute(statement.order_by(*ordering).limit(page_size + 1))
        return list(result.scalars().unique())

    @staticmethod
    def _after_cursor(sort: ReviewSort, cursor: dict, rank=None):
        timestamp = cursor_timestamp(cursor)
        review_id = cursor["id"]
        def after_timestamp(descending: bool):
            if timestamp is None:
                return and_(Review.publication_timestamp.is_(None), Review.id > review_id)
            compare = Review.publication_timestamp < timestamp if descending else Review.publication_timestamp > timestamp
            return or_(Review.publication_timestamp.is_(None), compare, and_(Review.publication_timestamp == timestamp, Review.id > review_id))
        if sort == ReviewSort.RELEVANT:
            relevance_rank = cursor.get("rank")
            if relevance_rank is None:
                return and_(rank.rank.is_(None), after_timestamp(True))
            return or_(rank.rank.is_(None), rank.rank > relevance_rank, and_(rank.rank == relevance_rank, after_timestamp(True)))
        if sort == ReviewSort.RECENT:
            return after_timestamp(True)
        if sort == ReviewSort.OLDEST:
            return after_timestamp(False)
        rating = cursor.get("rating")
        timestamp_clause = after_timestamp(True)
        if rating is None:
            return and_(Review.rating.is_(None), timestamp_clause)
        rating_clause = Review.rating < rating if sort == ReviewSort.RATING_HIGH else Review.rating > rating
        return or_(Review.rating.is_(None), rating_clause, and_(Review.rating == rating, timestamp_clause))

    async def list_for_place_by_ids(
        self,
        place: Place,
        review_ids: set,
        sort: ReviewSort = ReviewSort.RECENT,
        relevance_snapshot_id=None,
    ) -> list[Review]:
        if not review_ids:
            return []
        statement, ordering, _rank = self._ordered_statement(place, None, sort, relevance_snapshot_id)
        result = await self.session.execute(statement.where(Review.id.in_(review_ids)).order_by(*ordering))
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
        rich_changed = False
        outcome = "created"
        if review is None:
            review = Review(place_id=place.id, normalized_content_hash=content_hash)
            self.session.add(review)
            review.first_fetched_at = utcnow()
        else:
            rich_changed = self._has_rich_changes(review, item)
            outcome = "changed" if self._has_material_changes(review, item, content_hash) or rich_changed else "unchanged"
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
        attached_origin = await self._attach_origin(review, origin) if origin else None
        if origin is not None:
            reviewer = await ReviewerRepository(self.session).upsert_from_restaurant_review(item, origin)
            if reviewer is not None:
                review.reviewer_id = reviewer.id
            if origin.provider_review_id:
                review.google_review_id = origin.provider_review_id
            review.seen_via_restaurant_at = utcnow()
        if origin is not None and origin.provider_name == "serpapi":
            if item.details.state == "valid":
                review.details = item.details.value
            if item.translated_details.state == "valid":
                review.translated_details = item.translated_details.value
        image_changed = False
        if attached_origin is not None and item.images.state == "valid":
            image_changed = await self._sync_images(review, attached_origin, item.images)
        if not created and image_changed:
            outcome = "changed"
        if rich_changed or image_changed or (created and self._has_valid_rich_section(item)):
            review.rich_data_updated_at = utcnow()
        await self.session.flush()
        return review, outcome

    def _has_material_changes(self, review: Review, item: NormalizedReview, content_hash: str) -> bool:
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
                matching_origin.provider_publication_timestamp != item.origin.provider_publication_timestamp,
                matching_origin.provider_edit_timestamp != item.origin.provider_edit_timestamp,
            ]
        )

    def _has_rich_changes(self, review: Review, item: NormalizedReview) -> bool:
        origin = item.origin
        if origin is None:
            return False
        existing = self._matching_origin(review, origin)
        if existing is None:
            return self._has_valid_rich_section(item)
        changed = False
        if origin.details.state == "valid" and existing.provider_details != origin.details.value:
            changed = True
        if origin.translated_details.state == "valid" and existing.provider_translated_details != origin.translated_details.value:
            changed = True
        if origin.provider_name == "serpapi":
            if item.details.state == "valid" and review.details != item.details.value:
                changed = True
            if item.translated_details.state == "valid" and review.translated_details != item.translated_details.value:
                changed = True
        return changed

    @staticmethod
    def _has_valid_rich_section(item: NormalizedReview) -> bool:
        return any(section.state == "valid" for section in (item.details, item.translated_details, item.images))

    @staticmethod
    def _matching_origin(review: Review, origin: NormalizedReviewOrigin) -> ReviewOrigin | None:
        for existing in getattr(review, "origins", []) or []:
            if existing.provider_name == origin.provider_name and existing.provider_review_id == origin.provider_review_id:
                return existing
        return None

    async def _attach_origin(self, review: Review, origin: NormalizedReviewOrigin) -> ReviewOrigin:
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
        existing.local_guide = origin.local_guide
        existing.provider_review_count = origin.provider_review_count
        existing.provider_photo_count = origin.provider_photo_count
        existing.provider_publication_timestamp = origin.provider_publication_timestamp
        existing.provider_edit_timestamp = origin.provider_edit_timestamp
        if origin.details.state == "valid":
            existing.provider_details = origin.details.value
        if origin.translated_details.state == "valid":
            existing.provider_translated_details = origin.translated_details.value
        existing.fetched_at = utcnow()
        await self.session.flush()
        return existing

    async def _sync_images(self, review: Review, origin: ReviewOrigin, section: RichSection) -> bool:
        incoming = section.value if isinstance(section.value, list) else []
        result = await self.session.execute(
            select(ReviewImage).where(ReviewImage.review_origin_id == origin.id)
        )
        existing_by_url = {image.provider_image_url: image for image in result.scalars()}
        now = utcnow()
        changed = False
        incoming_urls = set(incoming)
        for position, url in enumerate(incoming):
            image = existing_by_url.get(url)
            if image is None:
                self.session.add(
                    ReviewImage(
                        review_id=review.id,
                        review_origin_id=origin.id,
                        provider_name=origin.provider_name,
                        provider_image_url=url,
                        position=position,
                        active=True,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )
                changed = True
                continue
            if not image.active or image.position != position:
                changed = True
            image.position = position
            image.active = True
            image.last_seen_at = now
        for url, image in existing_by_url.items():
            if image.active and url not in incoming_urls:
                image.active = False
                image.last_seen_at = now
                changed = True
        await self.session.flush()
        return changed

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

    async def increment_corpus_version(self, place: Place) -> None:
        place.review_corpus_version = (place.review_corpus_version or 1) + 1
        await self.session.flush()

    async def delete_for_place(self, place: Place) -> int:
        await self.session.execute(delete(ReviewTopic).where(ReviewTopic.place_id == place.id))
        result = await self.session.execute(delete(Review).where(Review.place_id == place.id))
        count = int(result.rowcount or 0)
        if count:
            place.review_corpus_version = (place.review_corpus_version or 1) + 1
        return count

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
