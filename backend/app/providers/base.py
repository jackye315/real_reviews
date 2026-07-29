from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.schemas.restaurants import RestaurantSearchPage, RestaurantSearchRequest


@dataclass(slots=True)
class NormalizedReviewOrigin:
    provider_name: str
    provider_review_id: str | None = None
    provider_place_id: str | None = None
    source_label: str | None = None
    source_url: str | None = None
    contributor_id: str | None = None
    author_profile_url: str | None = None
    author_avatar_url: str | None = None
    provider_publication_timestamp: datetime | None = None
    provider_edit_timestamp: datetime | None = None


@dataclass(slots=True)
class NormalizedReview:
    rating: int | None
    text: str | None
    original_text: str | None = None
    author_display_name: str | None = None
    author_avatar_url: str | None = None
    publication_timestamp: datetime | None = None
    last_edit_timestamp: datetime | None = None
    canonical_source_url: str | None = None
    source_label: str | None = None
    origin: NormalizedReviewOrigin | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedReviewTopic:
    provider_topic_id: str
    keyword: str
    mentions: int | None = None
    language_code: str | None = None
    rank: int = 0


@dataclass(slots=True)
class ReviewPage:
    reviews: list[NormalizedReview]
    topics: list[NormalizedReviewTopic] | None = None
    next_cursor: str | None = None
    successful_request_count: int = 0
    cached: bool = False


class RestaurantProvider(Protocol):
    async def search(self, request: RestaurantSearchRequest) -> RestaurantSearchPage:
        ...

    async def get_place(self, place_id: str):
        ...


class ReviewProvider(Protocol):
    async def fetch_page(
        self,
        place_id: str,
        cursor: str | None,
        page_size: int,
        sort: str,
    ) -> ReviewPage:
        ...
