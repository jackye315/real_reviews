import pytest
from pydantic import ValidationError

from app.schemas.reviews import RestaurantReviewFilterRequest


def test_sensitive_trait_filter_request_is_rejected():
    with pytest.raises(ValidationError):
        RestaurantReviewFilterRequest(content_filter="select reviews by ethnicity")


def test_unknown_reviewer_label_filter_is_rejected():
    with pytest.raises(ValidationError):
        RestaurantReviewFilterRequest(reviewer_label="unknown")
