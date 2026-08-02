from app.providers.serpapi import SerpApiReviewProvider
from app.utils.review_rich_data import parse_details, parse_images


def test_detail_parser_preserves_original_keys_and_omits_nulls():
    section = parse_details(
        {"Meal Type": "Dinner", "recommended-dishes": ["Pie", "Salad"], "unused": None},
        present=True,
    )
    assert section.state == "valid"
    assert section.value == {"Meal Type": "Dinner", "recommended-dishes": ["Pie", "Salad"]}


def test_detail_parser_rejects_nested_values_and_normalized_key_collisions():
    assert parse_details({"parking": {"lot": True}}, present=True).state == "malformed"
    assert parse_details({"Meal Type": "Dinner", "meal-type": "Lunch"}, present=True).state == "malformed"


def test_image_parser_requires_allowlisted_https_hosts_and_deduplicates_order():
    allowed = "https://lh3.googleusercontent.com/photo"
    section = parse_images([allowed, allowed, "https://lh4.googleusercontent.com/photo-2"], present=True)
    assert section.state == "valid"
    assert section.value == [allowed, "https://lh4.googleusercontent.com/photo-2"]
    assert parse_images(["https://example.lh3.googleusercontent.com/photo"], present=True).state == "malformed"
    assert parse_images(["http://lh3.googleusercontent.com/photo"], present=True).state == "malformed"


def test_serpapi_normalization_tracks_omitted_and_malformed_rich_sections():
    provider = SerpApiReviewProvider(api_key="test")
    omitted = provider._normalize_review({"rating": 5, "snippet": "Great", "source": "Google"}, "place")
    assert omitted.details.state == "omitted"
    assert omitted.images.state == "omitted"

    malformed = provider._normalize_review(
        {
            "rating": 5,
            "snippet": "Great",
            "source": "Google",
            "details": {"food": {"rating": 5}},
            "translated_details": {"food": "Excellent"},
            "images": ["https://not-allowed.example/photo"],
        },
        "place",
    )
    assert malformed.details.state == "malformed"
    assert malformed.translated_details.state == "valid"
    assert malformed.images.state == "malformed"
