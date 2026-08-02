from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import upstream_unconfigured
from app.providers.serpapi import SERPAPI_URL


@dataclass(slots=True)
class ContributorCandidate:
    review_id: str | None
    rating: int | None
    text: str | None
    date_text: str | None
    source_url: str | None
    data_id: str | None
    place_title: str | None
    place_type: str | None


@dataclass(slots=True)
class ContributorSnapshot:
    profile: dict[str, Any]
    reviews: list[ContributorCandidate]
    cached: bool


class SerpApiContributorReviewProvider:
    async def fetch(self, contributor_id: str) -> ContributorSnapshot:
        if not settings.serpapi_api_key:
            raise upstream_unconfigured("serpapi")
        params = {
            "engine": "google_maps_contributor_reviews",
            "contributor_id": contributor_id,
            "hl": settings.serpapi_language,
            "num": 200,
            "api_key": settings.serpapi_api_key,
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(SERPAPI_URL, params=params)
            response.raise_for_status()
            data = response.json()
        if data.get("error") or data.get("error_message"):
            raise RuntimeError("SerpApi contributor response reported an error")
        raw_profile = data.get("contributor") or data.get("contributor_info") or data.get("user") or {}
        reviews: list[ContributorCandidate] = []
        for item in data.get("reviews") or []:
            if not isinstance(item, dict):
                continue
            place = item.get("place_info") or {}
            rating = item.get("rating")
            reviews.append(
                ContributorCandidate(
                    review_id=_text(item.get("review_id") or item.get("id")),
                    rating=rating if isinstance(rating, int) and not isinstance(rating, bool) else None,
                    text=_text(item.get("snippet") or item.get("text")),
                    date_text=_text(item.get("date")),
                    source_url=_text(item.get("link") or item.get("review_link")),
                    data_id=_text(place.get("data_id")) if isinstance(place, dict) else None,
                    place_title=_text(place.get("title")) if isinstance(place, dict) else None,
                    place_type=_text(place.get("type")) if isinstance(place, dict) else None,
                )
            )
        metadata = data.get("search_metadata") or {}
        return ContributorSnapshot(profile=raw_profile if isinstance(raw_profile, dict) else {}, reviews=reviews, cached=metadata.get("cached") is True)


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
