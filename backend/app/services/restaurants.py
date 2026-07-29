from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.providers.google_places import GooglePlacesRestaurantProvider
from app.repositories.places import PlaceRepository
from app.schemas.restaurants import (
    PlaceSelectionRequest,
    RestaurantDetailResponse,
    RestaurantSearchPage,
    RestaurantSearchRequest,
)


class RestaurantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.places = PlaceRepository(session)
        self.google = GooglePlacesRestaurantProvider()

    async def persist_selection(self, request: PlaceSelectionRequest):
        place = await self.places.upsert_selection(request)
        await self.session.commit()
        return place

    async def search(self, request: RestaurantSearchRequest) -> RestaurantSearchPage:
        return await self.google.search(request)

    async def detail(self, place_id: str) -> RestaurantDetailResponse:
        place = await self.places.get_by_google_place_id(place_id)
        if place is None:
            raise AppError("PLACE_NOT_FOUND", "Place is not stored.", 404)
        count = await self.places.review_count(place)
        return RestaurantDetailResponse(place=place, stored_review_count=count)
