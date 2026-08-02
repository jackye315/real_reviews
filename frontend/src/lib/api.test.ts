import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadMoreReviews } from './api'

describe('API requests', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('keeps JSON content type when adding an idempotency header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ operation_id: 'operation-1' }) })
    vi.stubGlobal('fetch', fetchMock)

    await loadMoreReviews('place-1', 20, false, true, 'key-1')

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/reviews/load-more'), expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ 'Content-Type': 'application/json', 'Idempotency-Key': 'key-1' })
    }))
  })

  it('shows the first FastAPI validation message instead of raw validation JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      statusText: 'Unprocessable Entity',
      json: async () => ({ detail: [{ msg: 'Input should be a valid dictionary' }] })
    }))

    await expect(loadMoreReviews('place-1', 20, false, false, 'key-1')).rejects.toThrow('Input should be a valid dictionary')
  })
})
