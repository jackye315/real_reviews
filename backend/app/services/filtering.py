from __future__ import annotations

import asyncio
import json
from inspect import cleandoc
from uuid import UUID

import httpx
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError
from app.models.review import Review
from app.repositories.places import PlaceRepository
from app.repositories.reviews import ReviewRepository
from app.schemas.reviews import (
    REVIEWER_LABEL_OPTIONS,
    RestaurantReviewFilterRequest,
    ReviewFilterOptionsResponse,
    ReviewFilterResponse,
    ReviewerLabelOption,
)
from app.services.reviews import review_to_response, topic_to_response


class _LLMSelection(BaseModel):
    selected_review_ids: list[UUID]


class ReviewFilterService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.places = PlaceRepository(session) if session is not None else None
        self.reviews = ReviewRepository(session) if session is not None else None

    def options(self) -> ReviewFilterOptionsResponse:
        return ReviewFilterOptionsResponse(
            reviewer_label_options=[
                ReviewerLabelOption(value=value, label=label)
                for value, label in REVIEWER_LABEL_OPTIONS.items()
            ]
        )

    async def filter_restaurant(
        self, place_id: str, request: RestaurantReviewFilterRequest
    ) -> ReviewFilterResponse:
        if self.places is None or self.reviews is None:
            raise AppError("FILTER_SERVICE_UNBOUND", "Filter service requires a database session.", 500)
        place = await self.places.get_by_google_place_id(place_id)
        if place is None:
            raise AppError("PLACE_NOT_FOUND", "Place is not stored. Select or persist it first.", 404)

        candidates = await self.reviews.list_for_place(place, rating=request.rating, sort=request.sort)
        total = await self.reviews.count_for_place(place)
        candidate_count = len(candidates)
        topics = await self.reviews.list_topics_for_place(place)
        topics_payload = [topic_to_response(item) for item in topics]
        topics_fetched_at = max((item.snapshot_fetched_at for item in topics), default=None)

        if not request.reviewer_label and not request.content_filter:
            return ReviewFilterResponse(
                reviews=[review_to_response(item) for item in candidates],
                total=total,
                candidate_count=candidate_count,
                filtered_total=candidate_count,
                selected_review_ids=[item.id for item in candidates],
                rating_filter=request.rating,
                reviewer_label_filter=None,
                content_filter=None,
                sort=request.sort,
                llm_used=False,
                topics=topics_payload,
                topics_fetched_at=topics_fetched_at,
            )

        self._require_llm()
        selected_sets: list[set[UUID]] = []
        skipped_missing_label_count = 0

        if request.reviewer_label:
            name_result, skipped_missing_label_count = await self._filter_by_reviewer_label(
                candidates, REVIEWER_LABEL_OPTIONS[request.reviewer_label]
            )
            selected_sets.append(name_result)

        if request.content_filter:
            selected_sets.append(await self._filter_by_content(candidates, request.content_filter))

        selected_ids = set.intersection(*selected_sets) if selected_sets else {item.id for item in candidates}
        selected_reviews = await self.reviews.list_for_place_by_ids(place, selected_ids, sort=request.sort)
        return ReviewFilterResponse(
            reviews=[review_to_response(item) for item in selected_reviews],
            total=total,
            candidate_count=candidate_count,
            filtered_total=len(selected_reviews),
            selected_review_ids=[item.id for item in selected_reviews],
            skipped_missing_label_count=skipped_missing_label_count,
            rating_filter=request.rating,
            reviewer_label_filter=request.reviewer_label,
            content_filter=request.content_filter,
            sort=request.sort,
            llm_used=True,
            topics=topics_payload,
            topics_fetched_at=topics_fetched_at,
        )

    def _require_llm(self) -> None:
        if not settings.llm_base_url or not settings.llm_model:
            raise AppError("LLM_UNCONFIGURED", "LLM endpoint or model is not configured.", 503)

    async def _filter_by_reviewer_label(
        self, candidates: list[Review], target_label: str
    ) -> tuple[set[UUID], int]:
        named_candidates = [item for item in candidates if (item.author_display_name or "").strip()]
        skipped = len(candidates) - len(named_candidates)
        if not named_candidates:
            return set(), skipped
        semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

        async def run_batch(batch: list[Review]) -> list[UUID]:
            async with semaphore:
                return await self._name_batch(target_label, batch)

        results = await asyncio.gather(
            *(run_batch(batch) for batch in self._name_batches(named_candidates))
        )
        return {review_id for batch_result in results for review_id in batch_result}, skipped

    async def _filter_by_content(self, candidates: list[Review], content_filter: str) -> set[UUID]:
        text_candidates = [item for item in candidates if (item.text or item.original_text or "").strip()]
        if not text_candidates:
            return set()
        semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

        async def run_batch(batch: list[Review]) -> list[UUID]:
            async with semaphore:
                return await self._content_batch(content_filter, batch)

        results = await asyncio.gather(
            *(run_batch(batch) for batch in self._content_batches(text_candidates))
        )
        return {review_id for batch_result in results for review_id in batch_result}

    def _name_batches(self, reviews: list[Review]):
        batch: list[Review] = []
        size = 0
        max_count = settings.llm_name_batch_max_candidates
        for review in reviews:
            item_size = len(review.author_display_name or "") + 80
            if batch and (len(batch) >= max_count or size + item_size > settings.llm_batch_max_chars):
                yield batch
                batch = []
                size = 0
            batch.append(review)
            size += item_size
        if batch:
            yield batch

    def _content_batches(self, reviews: list[Review]):
        batch: list[Review] = []
        size = 0
        for review in reviews:
            item_size = len(review.text or review.original_text or "") + 200
            if batch and size + item_size > settings.llm_batch_max_chars:
                yield batch
                batch = []
                size = 0
            batch.append(review)
            size += item_size
        if batch:
            yield batch

    async def _name_batch(self, target_label: str, batch: list[Review]) -> list[UUID]:
        candidates_payload = [
            {"review_id": str(item.id), "author_display_name": item.author_display_name}
            for item in batch
        ]
        system = cleandoc("""
            DO NOT ECHO THE INPUT JSON FROM THE USER.
            Look at the provided target_label and candidates list and infer if the candidates are of the specified race from the target label by usng the candidiates author_display_name.
            If the reviewer is of the specified race, include their review_id in the result.

            Case, whitespace, punctuation, initials after the given name, and the target label appearing inside a full display name are not meaningful differences.
            For example Jackie Chan would match to chinese.
            David Kim would match to korean.
            When the race is uncertain, exclude the candidate.

            Return exactly this schema and nothing else: {"selected_review_ids": ["uuid"]}.
            If there are no matches, return {"selected_review_ids": []}.
            Do not include target_label, candidates, explanations, markdown, or prose.
        """)
        user = json.dumps(
            {"target_label": target_label, "candidates": candidates_payload}, ensure_ascii=False
        )
        return await self._run_llm_selection(system, user, {item.id for item in batch})

    async def _content_batch(self, content_filter: str, batch: list[Review]) -> list[UUID]:
        reviews_payload = [
            {
                "id": str(item.id),
                "text": item.text or item.original_text or "",
                "rating": item.rating,
                "publication_date": item.publication_timestamp.isoformat()
                if item.publication_timestamp
                else None,
            }
            for item in batch
        ]
        system = cleandoc("""
            You select restaurant reviews that explicitly match the user's content filter.
            Use only review text, rating, and publication date.
            Do not infer reviewer identity.

            Return exactly one JSON object and nothing else.
            The JSON object must have exactly this shape: {"selected_review_ids": ["uuid"]}.
            If there are no matches, return {"selected_review_ids": []}.
            Do not echo the input JSON.
            Do not include filter, reviews, explanations, markdown, or prose.
        """)
        user = json.dumps({"filter": content_filter, "reviews": reviews_payload}, ensure_ascii=False)
        return await self._run_llm_selection(system, user, {item.id for item in batch})

    async def _run_llm_selection(
        self, system: str, user: str, allowed_ids: set[UUID]
    ) -> list[UUID]:
        content = await self._chat_completion(system, user)
        try:
            parsed = _LLMSelection.model_validate_json(content)
        except Exception:
            retry_system = (
                system
                + " Your previous response was invalid because it did not return the required top-level selected_review_ids object. "
                + "Return exactly {\"selected_review_ids\": []} or {\"selected_review_ids\": [\"uuid\"]}; do not echo the input."
            )
            content = await self._chat_completion(retry_system, user)
            try:
                parsed = _LLMSelection.model_validate_json(content)
            except Exception as exc:
                raise AppError("LLM_INVALID_RESPONSE", "LLM returned invalid filter JSON.", 502) from exc
        unknown = [item for item in parsed.selected_review_ids if item not in allowed_ids]
        if unknown:
            raise AppError("LLM_UNKNOWN_REVIEW_ID", "LLM returned an unknown review ID.", 502)
        return list(dict.fromkeys(parsed.selected_review_ids))

    async def _chat_completion(self, system: str, user: str) -> str:
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_api_key}"
        base = str(settings.llm_base_url).rstrip("/")
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "review_selection",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "selected_review_ids": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["selected_review_ids"],
                        "additionalProperties": False
                    },
                    "strict": True
            }
            }
        }
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(f"{base}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]
