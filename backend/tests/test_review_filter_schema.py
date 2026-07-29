from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.reviews import ReviewFilterItem, ReviewFilterRequest


def test_sensitive_trait_filter_request_is_rejected():
    with pytest.raises(ValidationError):
        ReviewFilterRequest(
            filter_text="select reviews by ethnicity",
            reviews=[ReviewFilterItem(id=uuid4(), text="good noodles")],
        )
