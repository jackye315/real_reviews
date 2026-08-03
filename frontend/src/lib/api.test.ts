import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadMoreReviews, newIdempotencyKey, streamDishSummary } from './api'

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

  it('uses crypto.randomUUID when the page has a secure context', () => {
    vi.stubGlobal('crypto', { randomUUID: vi.fn(() => 'secure-context-uuid') })

    expect(newIdempotencyKey()).toBe('secure-context-uuid')
  })

  it('generates a UUID v4 when randomUUID is unavailable on an HTTP origin', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: (bytes: Uint8Array) => {
        bytes.set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
        return bytes
      }
    })

    expect(newIdempotencyKey()).toBe('00010203-0405-4607-8809-0a0b0c0d0e0f')
  })

  it('decodes streamed dish-summary deltas and returns the committed paragraph', async () => {
    const encoder = new TextEncoder()
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('{"type":"delta","text":"Reviewers praise "}\n'))
        controller.enqueue(encoder.encode('{"type":"delta","text":"the dumplings."}\n{"type":"done","summary":"Reviewers praise the dumplings."}\n'))
        controller.close()
      }
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, body }))
    const deltas: string[] = []

    const result = await streamDishSummary('place-1', ['Great dumplings.'], (delta) => deltas.push(delta))

    expect(deltas).toEqual(['Reviewers praise ', 'the dumplings.'])
    expect(result).toEqual({ summary: 'Reviewers praise the dumplings.' })
  })
})
