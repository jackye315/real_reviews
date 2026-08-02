from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.providers.base import NormalizedReview, ReviewPage
from app.providers.serpapi import ProviderCursorExpiredError
from app.schemas.reviews import ReviewSyncRequest
from app.services.reviews import ReviewService


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
    async def commit(self): self.commits += 1
    async def rollback(self): self.rollbacks += 1
    async def flush(self): pass
    async def refresh(self, _): pass


class FakeUsage:
    async def increment(self, *_, **__): pass


class FakeReviews:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.saved_cursors = []
        self.completed = []
        self.corpus_increments = 0
        self.upserted = 0
    async def list_for_place(self, *_args, **_kwargs): return []
    async def list_topics_for_place(self, *_): return []
    async def count_for_place(self, *_args, **_kwargs): return self.upserted
    async def create_sync_run(self, *_): return SimpleNamespace()
    async def complete_sync_run(self, *args): self.completed.append(args)
    async def upsert_normalized(self, _place, item):
        self.upserted += 1
        return SimpleNamespace(id=uuid4()), self.outcomes.pop(0)
    async def increment_corpus_version(self, _place): self.corpus_increments += 1
    async def upsert_topic_snapshot(self, *args): pass


class FakeProvider:
    def __init__(self, pages): self.pages = list(pages)
    async def fetch_page(self, *_):
        item = self.pages.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeOperationRepository:
    operation = None
    cancel_after_pages = False
    heartbeats = 0
    def __init__(self, _session):
        if FakeOperationRepository.operation is None:
            FakeOperationRepository.operation = SimpleNamespace(id=uuid4(), requested_units=2, status='reserved', successful_request_count=0, cached_response_count=0, failed_request_count=0, uncertain_request_count=0, released_reserved_count=0, collected_unique_count=0, result_metadata=None)
    async def find_by_idempotency(self, *_): return None
    async def reserve(self, **_): return FakeOperationRepository.operation, False
    async def mark_running(self, operation): operation.status = 'running'
    async def heartbeat(self, _): FakeOperationRepository.heartbeats += 1
    async def cancellation_requested(self, _): return FakeOperationRepository.cancel_after_pages and FakeOperationRepository.heartbeats >= 1
    async def settle_page(self, operation, successful=0, cached=0, failed=0, uncertain=0, collected=0):
        operation.successful_request_count += successful
        operation.cached_response_count += cached
        operation.failed_request_count += failed
        operation.uncertain_request_count += uncertain
        operation.collected_unique_count += collected
    async def finish(self, operation, status, stop_reason=None, error_summary=None):
        operation.status = status
        operation.stop_reason = stop_reason
        operation.error_summary = error_summary
        operation.released_reserved_count = max(0, operation.requested_units - operation.successful_request_count - operation.uncertain_request_count)
    async def get(self, _): return FakeOperationRepository.operation
    async def remaining_local_budget(self, _): return 100


def page(count, cursor):
    return ReviewPage(reviews=[NormalizedReview(rating=5, text=f'r{i}') for i in range(count)], next_cursor=cursor, successful_request_count=1)


def service(monkeypatch, pages, outcomes):
    FakeOperationRepository.operation = None
    FakeOperationRepository.cancel_after_pages = False
    FakeOperationRepository.heartbeats = 0
    monkeypatch.setattr('app.services.reviews.ProviderOperationRepository', FakeOperationRepository)
    s = ReviewService(FakeSession())
    async def get_place(_id): return SimpleNamespace(id=uuid4(), google_place_id='place-1', review_corpus_version=1)
    async def no_snapshot(): return None
    async def lock(_id): return True
    async def unlock(_id): return None
    state = SimpleNamespace(active_snapshot_id=None, pending_snapshot_id=None, next_rank=1, ranked_count=0, snapshot_status=None, relevance_fetched_at=None)
    async def collection_state(_place, _provider_sort='qualityScore'): return state
    async def save_cursor(_place, cursor, _provider_sort):
        s.reviews.saved_cursors.append(cursor)
        return state
    async def save_rank(*_args): pass
    s.places = SimpleNamespace(get_by_google_place_id=get_place)
    s.reviews = FakeReviews(outcomes)
    s.usage = FakeUsage()
    provider = FakeProvider(pages)
    s._review_provider = lambda _name: provider
    monkeypatch.setattr('app.services.reviews.account_snapshot', no_snapshot)
    s._try_place_lock = lock
    s._release_place_lock = unlock
    s._collection_state = collection_state
    s._store_provider_cursor = save_cursor
    s._store_relevance_rank = save_rank
    return s


@pytest.mark.asyncio
async def test_load_more_commits_completed_page_before_later_failure(monkeypatch):
    s = service(monkeypatch, [page(20, 'cursor-2'), RuntimeError('boom')], ['created'] * 20)
    with pytest.raises(RuntimeError):
        await s._sync('place-1', ReviewSyncRequest(target_count=40, force=True, confirm_cost=True, cursor='cursor-1'), False, 'k', operation_type='load_more')
    assert s.reviews.upserted == 20
    assert s.reviews.saved_cursors == ['cursor-2']
    assert FakeOperationRepository.operation.status == 'failed'
    assert FakeOperationRepository.operation.released_reserved_count == 1


@pytest.mark.asyncio
async def test_load_more_cancellation_preserves_completed_page_and_cursor(monkeypatch):
    s = service(monkeypatch, [page(20, 'cursor-2')], ['created'] * 20)
    FakeOperationRepository.cancel_after_pages = True
    response = await s._sync('place-1', ReviewSyncRequest(target_count=40, force=True, confirm_cost=True, cursor='cursor-1'), False, 'k', operation_type='load_more')
    assert response.status == 'cancelled'
    assert response.pagination_cursor == 'cursor-2'
    assert s.reviews.saved_cursors == ['cursor-2']
    assert FakeOperationRepository.operation.status == 'cancelled'


@pytest.mark.asyncio
async def test_load_more_expired_cursor_sets_recovery_metadata(monkeypatch):
    s = service(monkeypatch, [ProviderCursorExpiredError()], [])
    response = await s._sync('place-1', ReviewSyncRequest(target_count=20, force=True, confirm_cost=True, cursor='bad'), False, 'k', operation_type='load_more')
    assert response.status == 'failed'
    assert FakeOperationRepository.operation.status == 'failed'
    assert FakeOperationRepository.operation.result_metadata['error_code'] == 'PROVIDER_CURSOR_EXPIRED'
    assert FakeOperationRepository.operation.result_metadata['recovery_available'] is True
