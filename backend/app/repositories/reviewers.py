from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utcnow
from app.models.reviewer import Reviewer
from app.providers.base import NormalizedReview, NormalizedReviewOrigin


class ReviewerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, reviewer_id) -> Reviewer | None:
        return (await self.session.execute(select(Reviewer).where(Reviewer.id == reviewer_id))).scalar_one_or_none()

    async def get_by_contributor_id(self, contributor_id: str | None) -> Reviewer | None:
        if not contributor_id:
            return None
        return (
            await self.session.execute(
                select(Reviewer).where(Reviewer.google_contributor_id == contributor_id)
            )
        ).scalar_one_or_none()

    async def upsert_from_restaurant_review(
        self, item: NormalizedReview, origin: NormalizedReviewOrigin
    ) -> Reviewer | None:
        if not origin.contributor_id:
            return None
        reviewer = await self.get_by_contributor_id(origin.contributor_id)
        if reviewer is None:
            reviewer = Reviewer(google_contributor_id=origin.contributor_id)
            self.session.add(reviewer)
        reviewer.display_name = item.author_display_name or reviewer.display_name
        reviewer.avatar_url = item.author_avatar_url or origin.author_avatar_url or reviewer.avatar_url
        reviewer.profile_url = origin.author_profile_url or reviewer.profile_url
        if origin.local_guide is not None:
            reviewer.local_guide = origin.local_guide
        if origin.provider_review_count is not None:
            reviewer.provider_review_count = origin.provider_review_count
        if origin.provider_photo_count is not None:
            reviewer.provider_photo_count = origin.provider_photo_count
        reviewer.profile_observed_at = utcnow()
        await self.session.flush()
        return reviewer
