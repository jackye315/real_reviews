import logging
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.errors import AppError
from app.models.review import Review
from app.services.filtering import ReviewFilterService


def make_review(author: str = "Jack L.", text: str = "great patio") -> Review:
    return Review(
        id=uuid4(),
        place_id=uuid4(),
        rating=5,
        text=text,
        author_display_name=author,
        publication_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        normalized_content_hash="hash",
    )


@pytest.mark.asyncio
async def test_name_filter_payload_excludes_review_content(monkeypatch):
    service = ReviewFilterService()
    review = make_review()
    captured = {}

    async def fake_chat(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return f'{{"selected_review_ids": ["{review.id}"]}}'

    monkeypatch.setattr(service, "_chat_completion", fake_chat)

    result = await service._name_batch("Jack", [review])

    assert result == [review.id]
    assert "Jackie" in captured["system"]
    assert "great patio" not in captured["user"]
    assert "rating" not in captured["user"]
    assert "publication_date" not in captured["user"]
    assert "author_display_name" in captured["user"]


@pytest.mark.asyncio
async def test_content_filter_payload_excludes_reviewer_label(monkeypatch):
    service = ReviewFilterService()
    review = make_review(author="Jack L.")
    captured = {}

    async def fake_chat(system: str, user: str) -> str:
        captured["user"] = user
        return f'{{"selected_review_ids": ["{review.id}"]}}'

    monkeypatch.setattr(service, "_chat_completion", fake_chat)

    result = await service._content_batch("patio", [review])

    assert result == [review.id]
    assert "great patio" in captured["user"]
    assert "Jack L." not in captured["user"]
    assert "author_display_name" not in captured["user"]


@pytest.mark.asyncio
async def test_llm_unknown_id_is_rejected(monkeypatch, caplog):
    service = ReviewFilterService()
    review = make_review()
    unknown = uuid4()

    async def fake_chat(system: str, user: str) -> str:
        return f'{{"selected_review_ids": ["{unknown}"]}}'

    monkeypatch.setattr(service, "_chat_completion", fake_chat)

    with caplog.at_level(logging.WARNING, logger="app.services.filtering"):
        with pytest.raises(AppError) as exc:
            await service._name_batch("Jack", [review])

    assert exc.value.detail["code"] == "LLM_UNKNOWN_REVIEW_ID"
    assert str(unknown) in caplog.text
    assert str(review.id) in caplog.text
