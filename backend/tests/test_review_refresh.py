from datetime import datetime, timezone
from uuid import uuid4

from app.models.review import Review
from app.models.review_origin import ReviewOrigin
from app.providers.base import NormalizedReview, NormalizedReviewOrigin
from app.repositories.reviews import ReviewRepository
from app.services.reviews import estimate_serpapi_requests


def normalized_review(text: str = "great pizza", rating: int = 5) -> NormalizedReview:
    published = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return NormalizedReview(
        rating=rating,
        text=text,
        original_text=text,
        author_display_name="A Reviewer",
        author_avatar_url="https://example.test/avatar.jpg",
        publication_timestamp=published,
        last_edit_timestamp=None,
        canonical_source_url="https://example.test/review",
        origin=NormalizedReviewOrigin(
            provider_name="serpapi",
            provider_review_id="review-1",
            provider_place_id="place-1",
            source_label="Google",
            source_url="https://example.test/review",
            contributor_id="contributor-1",
            author_profile_url="https://example.test/profile",
            author_avatar_url="https://example.test/avatar.jpg",
            provider_publication_timestamp=published,
        ),
    )


def stored_review() -> Review:
    item = normalized_review()
    review = Review(id=uuid4(), place_id=uuid4(), normalized_content_hash="8a8f8c")
    review.rating = item.rating
    review.text = item.text
    review.original_text = item.original_text
    review.author_display_name = item.author_display_name
    review.author_avatar_url = item.author_avatar_url
    review.publication_timestamp = item.publication_timestamp
    review.last_edit_timestamp = item.last_edit_timestamp
    review.canonical_source_url = item.canonical_source_url
    review.origins = [
        ReviewOrigin(
            provider_name="serpapi",
            provider_review_id="review-1",
            provider_place_id="place-1",
            source_label="Google",
            source_url="https://example.test/review",
            contributor_id="contributor-1",
            author_profile_url="https://example.test/profile",
            author_avatar_url="https://example.test/avatar.jpg",
            provider_publication_timestamp=item.publication_timestamp,
        )
    ]
    return review


def test_serpapi_estimate_accounts_for_smaller_first_page():
    assert estimate_serpapi_requests(8) == 1
    assert estimate_serpapi_requests(9) == 2
    assert estimate_serpapi_requests(50) == 4


def test_material_change_detection_marks_identical_review_unchanged():
    repo = ReviewRepository(session=None)  # type: ignore[arg-type]
    assert repo._has_material_changes(stored_review(), normalized_review(), "8a8f8c") is False


def test_material_change_detection_marks_edited_review_changed():
    repo = ReviewRepository(session=None)  # type: ignore[arg-type]
    assert repo._has_material_changes(stored_review(), normalized_review(text="updated pizza"), "different") is True
