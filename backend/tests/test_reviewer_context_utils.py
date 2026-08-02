from datetime import datetime, timezone

from app.utils.contributor_dates import parse_contributor_date
from app.utils.venue_types import classify_current_place_types, classify_food_drink_decision, classify_food_drink_type


def test_food_drink_classifier_accepts_specific_restaurants_and_rejects_unknowns():
    pizza = classify_food_drink_type(" Pizza restaurant ")
    assert pizza and pizza.normalized == "pizza_restaurant" and pizza.family == "restaurant"
    assert classify_food_drink_type("Café").normalized == "cafe"  # type: ignore[union-attr]
    assert classify_food_drink_type("Patisserie") is None
    assert classify_food_drink_decision("Hotel").decision == "rejected_explicit_non_food"
    assert classify_food_drink_decision("Patisserie").decision == "rejected_unknown_or_ambiguous_type"
    assert classify_current_place_types(["food", "restaurant", "thai_restaurant"]).normalized == "thai_restaurant"  # type: ignore[union-attr]


def test_relative_contributor_dates_keep_edited_basis_and_unknowns():
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    edited = parse_contributor_date("Edited a year ago", now)
    assert edited.approximate and edited.precision == "year" and edited.basis == "edited_or_displayed"
    assert parse_contributor_date("sometime", now).precision == "unknown"
