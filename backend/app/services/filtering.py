from __future__ import annotations

import asyncio
import json
from uuid import UUID

import httpx

from app.core.config import settings
from app.core.errors import AppError
from app.schemas.reviews import ReviewFilterRequest, ReviewFilterResponse


class ReviewFilterService:
    async def filter(self, request: ReviewFilterRequest) -> ReviewFilterResponse:
        if not settings.llm_base_url or not settings.llm_model:
            raise AppError("LLM_UNCONFIGURED", "LLM endpoint or model is not configured.", 503)
        allowed_ids = {item.id for item in request.reviews}
        semaphore = asyncio.Semaphore(settings.llm_max_concurrency)

        async def run_batch(batch):
            async with semaphore:
                return await self._filter_batch(request.filter_text, batch, allowed_ids)

        results = await asyncio.gather(*(run_batch(batch) for batch in self._batches(request)))
        selected: list[UUID] = [review_id for batch_result in results for review_id in batch_result]
        deduped = list(dict.fromkeys(selected))
        return ReviewFilterResponse(selected_review_ids=deduped, llm_used=True)

    def _batches(self, request: ReviewFilterRequest):
        current = []
        size = 0
        for item in request.reviews:
            item_size = len(item.text or "") + 200
            if current and size + item_size > settings.llm_batch_max_chars:
                yield current
                current = []
                size = 0
            current.append(item)
            size += item_size
        if current:
            yield current

    async def _filter_batch(self, filter_text: str, batch, allowed_ids: set[UUID]) -> list[UUID]:
        reviews_payload = [
            {
                "id": str(item.id),
                "text": item.text,
                "rating": item.rating,
                "publication_date": item.publication_date.isoformat() if item.publication_date else None,
            }
            for item in batch
        ]
        system = (
            "You select restaurant reviews that explicitly match the user's content filter. "
            "Use only review text, rating, and publication date. Do not infer reviewer identity. "
            "Return strict JSON only with shape {\"selected_review_ids\": [\"uuid\"]}."
        )
        user = json.dumps({"filter": filter_text, "reviews": reviews_payload}, ensure_ascii=False)
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
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            response = await client.post(f"{base}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
            ids = [UUID(value) for value in parsed.get("selected_review_ids", [])]
        except Exception as exc:
            raise AppError("LLM_INVALID_RESPONSE", "LLM returned invalid filter JSON.", 502) from exc
        unknown = [item for item in ids if item not in allowed_ids]
        if unknown:
            raise AppError("LLM_UNKNOWN_REVIEW_ID", "LLM returned an unknown review ID.", 502)
        return ids
