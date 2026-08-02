from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

CLASSIFIER_VERSION = "food_drink_v1"


@dataclass(frozen=True, slots=True)
class VenueType:
    normalized: str
    family: str


def normalize_provider_type(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value).casefold()
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("&", " and ").replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True, slots=True)
class VenueClassification:
    venue_type: VenueType | None
    decision: str


# These are known non-food provider values. Everything else rejected remains unknown
# rather than being guessed from a title, address, or review text.
_EXPLICIT_NON_FOOD_TYPES = {
    "hotel", "resort", "lodge", "supermarket", "grocery store", "convenience store",
    "store", "market", "catering service", "event venue", "wedding venue",
}


def classify_food_drink_decision(value: str | None) -> VenueClassification:
    venue_type = classify_food_drink_type(value)
    if venue_type is not None:
        return VenueClassification(venue_type, "accepted_food_and_drink")
    return VenueClassification(
        None,
        "rejected_explicit_non_food" if normalize_provider_type(value) in _EXPLICIT_NON_FOOD_TYPES else "rejected_unknown_or_ambiguous_type",
    )


def classify_food_drink_type(value: str | None) -> VenueType | None:
    raw = normalize_provider_type(value)
    if raw == "restaurant":
        return VenueType("restaurant", "restaurant")
    if raw.endswith(" restaurant"):
        return VenueType(f"{raw.replace(' ', '_')}", "restaurant")
    mapping = {
        "diner": ("diner", "restaurant"),
        "bistro": ("bistro", "restaurant"),
        "cafeteria": ("cafeteria", "restaurant"),
        "food court": ("food_court", "restaurant"),
        "bar and grill": ("bar_and_grill", "restaurant"),
        "cafe": ("cafe", "cafe"),
        "coffee shop": ("coffee_shop", "cafe"),
        "bar": ("bar", "bar_or_pub"),
        "pub": ("pub", "bar_or_pub"),
        "brewery": ("brewery", "brewery_or_winery"),
        "winery": ("winery", "brewery_or_winery"),
        "bakery": ("bakery", "bakery_or_dessert"),
        "dessert shop": ("dessert_shop", "bakery_or_dessert"),
        "ice cream shop": ("ice_cream_shop", "bakery_or_dessert"),
    }
    result = mapping.get(raw)
    return VenueType(*result) if result else None


def classify_current_place_types(values: list[str] | None) -> VenueType | None:
    types = values or []
    classified = [classify_food_drink_type(value) for value in types]
    specific_restaurants = [item for item in classified if item and item.family == "restaurant" and item.normalized != "restaurant"]
    if specific_restaurants:
        return specific_restaurants[0]
    non_restaurant = [item for item in classified if item and item.family != "restaurant"]
    if non_restaurant:
        return non_restaurant[0]
    return next((item for item in classified if item and item.normalized == "restaurant"), None)
