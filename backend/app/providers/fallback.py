from __future__ import annotations

from app.providers.base import ReviewPage, ReviewProvider


class FallbackReviewProvider:
    def __init__(self, primary: ReviewProvider, fallback: ReviewProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    async def fetch_page(
        self, place_id: str, cursor: str | None, page_size: int, sort: str
    ) -> ReviewPage:
        try:
            page = await self.primary.fetch_page(place_id, cursor, page_size, sort)
            if page.reviews or cursor:
                return page
        except Exception:
            if cursor:
                raise
        return await self.fallback.fetch_page(place_id, None, min(page_size, 5), sort)
