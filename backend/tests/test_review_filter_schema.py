import pytest
from pydantic import ValidationError

from app.schemas.reviews import RestaurantReviewFilterRequest
from app.services.filtering import ReviewFilterService


def test_sensitive_trait_filter_request_is_rejected():
    with pytest.raises(ValidationError):
        RestaurantReviewFilterRequest(content_filter="select reviews by ethnicity")


def test_only_neutral_reviewer_labels_are_returned():
    options = ReviewFilterService().options().reviewer_label_options
    assert [(option.value, option.label) for option in options] == [
        ("chinese", "Chinese"),
        ("korean", "Korean"),
        ("japanese", "Japanese"),
        ("american", "American"),
        ("italian", "Italian"),
    ]


def test_unknown_reviewer_label_filter_is_rejected():
    with pytest.raises(ValidationError):
        RestaurantReviewFilterRequest(reviewer_label="unknown")
