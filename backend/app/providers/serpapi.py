from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import upstream_unconfigured
from app.providers.base import NormalizedReview, NormalizedReviewOrigin, NormalizedReviewTopic, ReviewPage
from app.utils.dates import parse_datetime
from app.utils.review_ids import google_review_id_from_url

SERPAPI_URL = "https://serpapi.com/search.json"


class SerpApiReviewProvider:
    provider_name = "serpapi"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.serpapi_api_key

    async def fetch_page(
        self, place_id: str, cursor: str | None, page_size: int, sort: str
    ) -> ReviewPage:
        if not self.api_key:
            raise upstream_unconfigured("serpapi")
        params: dict[str, Any] = {
            "engine": "google_maps_reviews",
            "place_id": place_id,
            "api_key": self.api_key,
            "sort_by": sort,
            "hl": settings.serpapi_language,
        }
        if cursor:
            params["next_page_token"] = cursor
            if page_size:
                params["num"] = min(page_size, 20)
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(SERPAPI_URL, params=params)
            response.raise_for_status()
            data = response.json()
        reviews = [
            self._normalize_review(item, place_id)
            for item in data.get("reviews", [])
            if (item.get("source") or "Google") == "Google"
        ]
        topics = self._normalize_topics(data.get("topics")) if not cursor and "topics" in data else None
        pagination = data.get("serpapi_pagination") or {}
        search_metadata = data.get("search_metadata") or {}
        cached = search_metadata.get("cached") is True
        successful = 0 if cached else 1
        return ReviewPage(
            reviews=reviews,
            topics=topics,
            next_cursor=pagination.get("next_page_token"),
            successful_request_count=successful,
            cached=cached,
        )

    def _normalize_topics(self, raw_topics: Any) -> list[NormalizedReviewTopic]:
        if not isinstance(raw_topics, list):
            return []
        topics: list[NormalizedReviewTopic] = []
        seen_ids: set[str] = set()
        for item in raw_topics:
            if not isinstance(item, dict):
                continue
            provider_topic_id = str(item.get("id") or "").strip()
            keyword = str(item.get("keyword") or "").strip()
            if not provider_topic_id or not keyword or provider_topic_id in seen_ids:
                continue
            seen_ids.add(provider_topic_id)
            mentions = self._normalize_mentions(item.get("mentions"))
            topics.append(
                NormalizedReviewTopic(
                    provider_topic_id=provider_topic_id,
                    keyword=keyword,
                    mentions=mentions,
                    language_code=settings.serpapi_language or None,
                    rank=len(topics),
                )
            )
        return topics

    @staticmethod
    def _normalize_mentions(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value if value >= 0 else None
        if isinstance(value, float):
            return int(value) if value >= 0 else None
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            if cleaned.isdigit():
                return int(cleaned)
        return None

    def _normalize_review(self, item: dict[str, Any], place_id: str) -> NormalizedReview:
        published = parse_datetime(
            item.get("iso_date")
            or item.get("date")
            or item.get("published_at")
            or item.get("time")
            or item.get("timestamp")
        )
        edited = parse_datetime(item.get("iso_date_of_last_edit") or item.get("last_edited") or item.get("edited_at"))
        text = item.get("snippet") or item.get("text") or item.get("extracted_snippet", {}).get("original")
        original_text = item.get("original") or item.get("translated_snippet")
        source_url = item.get("link") or item.get("review_link")
        review_id = item.get("review_id") or item.get("id") or google_review_id_from_url(source_url)
        user = item.get("user") or {}
        contributor_id = item.get("user_id") or user.get("contributor_id") or user.get("id")
        author_name = item.get("user_name") or user.get("name")
        author_link = item.get("user_link") or user.get("link")
        author_thumbnail = item.get("thumbnail") or user.get("thumbnail")
        origin = NormalizedReviewOrigin(
            provider_name=self.provider_name,
            provider_review_id=review_id,
            provider_place_id=place_id,
            source_label=item.get("source") or "Google",
            source_url=source_url,
            contributor_id=contributor_id,
            author_profile_url=author_link,
            author_avatar_url=author_thumbnail,
            provider_publication_timestamp=published,
            provider_edit_timestamp=edited,
        )
        rating = item.get("rating")
        if isinstance(rating, float):
            rating = round(rating)
        return NormalizedReview(
            rating=rating,
            text=text,
            original_text=original_text,
            author_display_name=author_name,
            author_avatar_url=author_thumbnail,
            publication_timestamp=published,
            last_edit_timestamp=edited,
            canonical_source_url=source_url,
            source_label=item.get("source") or "Google",
            origin=origin,
            raw=item,
        )
