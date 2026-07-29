from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.place import Place
from app.models.review import Review
from app.schemas.restaurants import PlaceSelectionRequest, RestaurantSearchResult


class PlaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_google_place_id(self, google_place_id: str) -> Place | None:
        result = await self.session.execute(
            select(Place).where(Place.google_place_id == google_place_id)
        )
        return result.scalar_one_or_none()

    async def upsert_selection(self, request: PlaceSelectionRequest) -> Place:
        place = await self.get_by_google_place_id(request.google_place_id)
        if place is None:
            place = Place(google_place_id=request.google_place_id, display_name=request.display_name)
            self.session.add(place)
        place.display_name = request.display_name
        place.formatted_address = request.formatted_address
        place.latitude = request.location.latitude if request.location else None
        place.longitude = request.location.longitude if request.location else None
        place.viewport = request.viewport
        place.place_types = request.place_types
        place.google_maps_url = request.google_maps_url or f"https://www.google.com/maps/place/?q=place_id:{request.google_place_id}"
        await self.session.flush()
        return place

    async def upsert_search_result(self, result: RestaurantSearchResult) -> Place:
        return await self.upsert_selection(
            PlaceSelectionRequest(
                google_place_id=result.google_place_id,
                display_name=result.display_name,
                formatted_address=result.formatted_address,
                location={"latitude": result.latitude, "longitude": result.longitude}
                if result.latitude is not None and result.longitude is not None
                else None,
                viewport=result.viewport,
                place_types=result.place_types or [],
                google_maps_url=result.google_maps_url,
            )
        )

    async def review_count(self, place: Place) -> int:
        result = await self.session.execute(select(func.count(Review.id)).where(Review.place_id == place.id))
        return int(result.scalar_one())
