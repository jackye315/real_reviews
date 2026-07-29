from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.errors import upstream_unconfigured
from app.providers.base import NormalizedReview, NormalizedReviewOrigin, ReviewPage
from app.schemas.restaurants import RestaurantSearchPage, RestaurantSearchRequest, RestaurantSearchResult
from app.utils.dates import parse_datetime
from app.utils.geo import distance_meters
from app.utils.review_ids import google_review_id_from_resource_name

GOOGLE_PLACES_BASE = "https://places.googleapis.com/v1"


class GooglePlacesRestaurantProvider:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.google_maps_server_api_key

    async def search(self, request: RestaurantSearchRequest) -> RestaurantSearchPage:
        if not self.api_key:
            raise upstream_unconfigured("google")
        payload: dict[str, Any] = {
            "textQuery": request.query,
            "includedType": "restaurant",
            "strictTypeFiltering": False,
            "pageSize": request.page_size,
        }
        if request.page_token:
            payload["pageToken"] = request.page_token
        if request.latitude is not None and request.longitude is not None:
            payload["locationBias"] = {
                "circle": {
                    "center": {"latitude": request.latitude, "longitude": request.longitude},
                    "radius": float(request.radius_meters or 5000),
                }
            }
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": ",".join(
                [
                    "places.id",
                    "places.displayName",
                    "places.formattedAddress",
                    "places.location",
                    "places.viewport",
                    "places.types",
                    "places.googleMapsUri",
                    "places.rating",
                    "places.userRatingCount",
                    "nextPageToken",
                ]
            ),
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(f"{GOOGLE_PLACES_BASE}/places:searchText", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        results = [self._to_search_result(place, request) for place in data.get("places", [])]
        if request.latitude is not None and request.longitude is not None:
            results.sort(
                key=lambda result: result.distance_meters
                if result.distance_meters is not None
                else 10**12
            )
        return RestaurantSearchPage(results=results, next_page_token=data.get("nextPageToken"))

    async def get_place(self, place_id: str) -> RestaurantSearchResult:
        if not self.api_key:
            raise upstream_unconfigured("google")
        resource = place_id if place_id.startswith("places/") else f"places/{place_id}"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "id,displayName,formattedAddress,location,viewport,types,googleMapsUri",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(f"{GOOGLE_PLACES_BASE}/{resource}", headers=headers)
            response.raise_for_status()
        return self._to_search_result(response.json())

    @staticmethod
    def _to_search_result(
        place: dict[str, Any], request: RestaurantSearchRequest | None = None
    ) -> RestaurantSearchResult:
        location = place.get("location") or {}
        display_name = place.get("displayName") or {}
        google_place_id = place.get("id", "").removeprefix("places/")
        distance = None
        if (
            request is not None
            and request.latitude is not None
            and request.longitude is not None
            and location.get("latitude") is not None
            and location.get("longitude") is not None
        ):
            distance = distance_meters(
                request.latitude,
                request.longitude,
                location["latitude"],
                location["longitude"],
            )
        return RestaurantSearchResult(
            google_place_id=google_place_id,
            display_name=display_name.get("text") or google_place_id,
            formatted_address=place.get("formattedAddress"),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            viewport=place.get("viewport"),
            place_types=place.get("types"),
            google_maps_url=place.get("googleMapsUri"),
            rating=place.get("rating"),
            user_rating_count=place.get("userRatingCount"),
            distance_meters=distance,
        )


class GooglePlacesReviewProvider:
    provider_name = "google_places"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.google_maps_server_api_key

    async def fetch_page(
        self, place_id: str, cursor: str | None, page_size: int, sort: str
    ) -> ReviewPage:
        if not self.api_key:
            raise upstream_unconfigured("google")
        if cursor:
            return ReviewPage(reviews=[], next_cursor=None, successful_request_count=0)
        resource = place_id if place_id.startswith("places/") else f"places/{place_id}"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": "reviews",
        }
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.get(f"{GOOGLE_PLACES_BASE}/{resource}", headers=headers)
            response.raise_for_status()
            data = response.json()
        reviews = [self._normalize_review(item, place_id) for item in data.get("reviews", [])[:page_size]]
        return ReviewPage(reviews=reviews, next_cursor=None, successful_request_count=1)

    def _normalize_review(self, item: dict[str, Any], place_id: str) -> NormalizedReview:
        author = item.get("authorAttribution") or {}
        text_obj = item.get("text") or item.get("originalText") or {}
        original_obj = item.get("originalText") or {}
        name = item.get("name")
        published = parse_datetime(item.get("publishTime"))
        edited = parse_datetime(item.get("relativePublishTimeDescription"))
        origin = NormalizedReviewOrigin(
            provider_name=self.provider_name,
            provider_review_id=google_review_id_from_resource_name(name),
            provider_place_id=place_id,
            source_label="Google",
            source_url=item.get("googleMapsUri"),
            author_profile_url=author.get("uri"),
            author_avatar_url=author.get("photoUri"),
            provider_publication_timestamp=published,
            provider_edit_timestamp=edited,
        )
        return NormalizedReview(
            rating=item.get("rating"),
            text=text_obj.get("text") if isinstance(text_obj, dict) else None,
            original_text=original_obj.get("text") if isinstance(original_obj, dict) else None,
            author_display_name=author.get("displayName"),
            author_avatar_url=author.get("photoUri"),
            publication_timestamp=published,
            last_edit_timestamp=edited,
            canonical_source_url=item.get("googleMapsUri"),
            source_label="Google",
            origin=origin,
            raw=item,
        )
