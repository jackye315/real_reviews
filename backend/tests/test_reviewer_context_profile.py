from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from app.models.place import Place
from app.models.review import Review
from app.models.reviewer import Reviewer
from app.schemas.reviewers import ReviewerComparisonResponse
from app.services.reviewer_context import ReviewerContextService


class _NoActiveOperationResult:
    def scalar_one_or_none(self):
        return None


class _ProfileSession:
    async def execute(self, _statement):
        return _NoActiveOperationResult()


class _ComparisonResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ComparisonSession:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, _statement):
        return _ComparisonResult(self._rows)


async def test_profile_returns_broader_comparison_when_exact_sample_is_empty():
    """Regression contract: an exact zero must not erase broader retained history."""
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    reviewer = Reviewer(
        id=uuid4(),
        display_name="Synthetic reviewer",
        context_generation=3,
        context_status="available",
        context_fetched_at=now,
        contributor_profile={},
    )
    place = Place(
        id=uuid4(),
        google_place_id="synthetic-tibetan-place",
        display_name="Synthetic Tibetan Restaurant",
        normalized_venue_type="tibetan_restaurant",
        comparison_family="restaurant",
    )
    current = Review(
        id=uuid4(),
        place_id=place.id,
        reviewer_id=reviewer.id,
        rating=2,
        text="Synthetic current review",
        normalized_content_hash="0" * 64,
        first_fetched_at=now,
        last_seen_at=now,
        publication_date_is_approximate=False,
        suspected_duplicate=False,
        details={},
        translated_details={},
    )
    current.place = place
    current.origins = []
    current.images = []

    exact = ReviewerComparisonResponse(
        current_rating=2,
        match_level="exact_type",
        normalized_venue_type="tibetan_restaurant",
        comparison_family="restaurant",
        time_window="two_years",
        sample_size=0,
        rating_distribution={str(rating): 0 for rating in range(1, 6)},
        context_generation=3,
    )
    broader = ReviewerComparisonResponse(
        current_rating=2,
        match_level="comparison_family",
        normalized_venue_type="tibetan_restaurant",
        comparison_family="restaurant",
        time_window="two_years",
        sample_size=15,
        average_rating=4.7,
        median_rating=5,
        sample_variance=1.0,
        standard_deviation=1.0,
        difference_from_average=-2.7,
        rating_distribution={"1": 1, "2": 0, "3": 0, "4": 1, "5": 13},
        context_generation=3,
    )

    service = ReviewerContextService(_ProfileSession())  # type: ignore[arg-type]
    service._reviewer_and_current = AsyncMock(return_value=(reviewer, current))  # type: ignore[method-assign]
    service.comparison = AsyncMock(side_effect=[exact, broader])  # type: ignore[method-assign]

    response = await service.profile(reviewer.id, current.id)

    assert response.comparison == exact
    assert response.broader_comparison == broader
    assert response.comparison.sample_size == 0
    assert response.broader_comparison.sample_size == 15
    assert service.comparison.await_count == 2
    assert service.comparison.await_args_list[0].args[2:4] == ("two_years", "exact_type")
    assert service.comparison.await_args_list[1].args[2:4] == (
        "two_years",
        "comparison_family",
    )


async def test_comparison_returns_all_matching_stored_review_bodies():
    now = datetime(2026, 8, 2, tzinfo=timezone.utc)
    reviewer = Reviewer(
        id=uuid4(),
        display_name="Synthetic reviewer",
        context_generation=4,
        context_status="available",
        context_fetched_at=now,
        contributor_profile={},
    )
    current_place = Place(
        id=uuid4(),
        google_place_id="current-place",
        display_name="Current Tibetan Restaurant",
        normalized_venue_type="tibetan_restaurant",
        comparison_family="restaurant",
    )
    current = Review(
        id=uuid4(),
        place_id=current_place.id,
        reviewer_id=reviewer.id,
        rating=2,
        normalized_content_hash="1" * 64,
        first_fetched_at=now,
        last_seen_at=now,
        publication_date_is_approximate=False,
        suspected_duplicate=False,
    )
    current.place = current_place

    rows = []
    for index in range(12):
        place = Place(
            id=uuid4(),
            display_name=f"Comparison restaurant {index + 1}",
            normalized_venue_type="restaurant",
            comparison_family="restaurant",
        )
        review = Review(
            id=uuid4(),
            place_id=place.id,
            reviewer_id=reviewer.id,
            rating=5,
            text=f"Stored canonical review body {index + 1}",
            original_text=f"Original review body {index + 1}",
            canonical_source_url=f"https://reviews.example/{index + 1}",
            provider_date_text=f"{index + 1} months ago",
            contributor_generation=4,
            normalized_content_hash=f"{index + 2:064x}",
            first_fetched_at=now,
            last_seen_at=now,
            publication_date_is_approximate=True,
            suspected_duplicate=False,
        )
        rows.append((review, place))

    service = ReviewerContextService(_ComparisonSession(rows))  # type: ignore[arg-type]
    response = await service.comparison(
        reviewer.id,
        current.id,
        "all_observed",
        "comparison_family",
        _validated=(reviewer, current),
    )

    assert response.sample_size == 12
    assert len(response.relevant_reviews) == 12
    assert response.relevant_reviews[0].text == "Stored canonical review body 1"
    assert response.relevant_reviews[-1].original_text == "Original review body 12"
