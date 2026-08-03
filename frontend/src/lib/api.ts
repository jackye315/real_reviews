import type {
  DishSummaryResponse,
  GoogleReviewSummary,
  LoadMoreOptions,
  PlaceResponse,
  ProviderOperation,
  ProviderUsage,
  RestaurantSearchPage,
  RestaurantDetailResponse,
  RestaurantSearchResult,
  ReviewFilterOptionsResponse,
  ReviewFilterResponse,
  ReviewListResponse,
  ReviewerContext,
  ReviewSort,
  ReviewSyncResponse
} from '../types/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) }
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail = payload?.detail
    const message = detail?.message ?? (Array.isArray(detail) ? detail[0]?.msg : detail) ?? response.statusText
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  return response.json() as Promise<T>
}

export async function persistSelection(selection: {
  google_place_id: string
  display_name: string
  formatted_address?: string | null
  location?: { latitude: number; longitude: number } | null
  viewport?: Record<string, unknown> | null
  place_types?: string[]
  google_maps_url?: string | null
}): Promise<PlaceResponse> {
  return requestJson<PlaceResponse>('/restaurants/selection', {
    method: 'POST',
    body: JSON.stringify(selection)
  })
}

export async function searchRestaurants(
  query: string,
  pageToken?: string | null,
  location?: { latitude: number; longitude: number } | null
): Promise<RestaurantSearchPage> {
  return requestJson<RestaurantSearchPage>('/restaurants/search', {
    method: 'POST',
    body: JSON.stringify({
      query,
      page_token: pageToken,
      latitude: location?.latitude,
      longitude: location?.longitude,
      page_size: 10
    })
  })
}

export async function persistSearchResult(result: RestaurantSearchResult): Promise<PlaceResponse> {
  return persistSelection({
    google_place_id: result.google_place_id,
    display_name: result.display_name,
    formatted_address: result.formatted_address,
    location:
      result.latitude !== null && result.latitude !== undefined && result.longitude !== null && result.longitude !== undefined
        ? { latitude: result.latitude, longitude: result.longitude }
        : null,
    viewport: result.viewport,
    place_types: result.place_types ?? [],
    google_maps_url: result.google_maps_url
  })
}

export async function getRestaurantDetail(placeId: string): Promise<RestaurantDetailResponse> {
  return requestJson<RestaurantDetailResponse>(`/restaurants/${encodeURIComponent(placeId)}`)
}

export async function generateDishSummary(placeId: string, reviewTexts: string[]): Promise<DishSummaryResponse> {
  return requestJson<DishSummaryResponse>(`/restaurants/${encodeURIComponent(placeId)}/dish-summary`, {
    method: 'POST', body: JSON.stringify({ review_texts: reviewTexts })
  })
}

export async function streamDishSummary(
  placeId: string,
  reviewTexts: string[],
  onDelta: (text: string) => void
): Promise<DishSummaryResponse> {
  const response = await fetch(`${API_BASE}/restaurants/${encodeURIComponent(placeId)}/dish-summary/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ review_texts: reviewTexts })
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const detail = payload?.detail
    const message = detail?.message ?? (Array.isArray(detail) ? detail[0]?.msg : detail) ?? response.statusText
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message))
  }
  if (!response.body) throw new Error('The local LLM stream is unavailable. Try again later.')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completedSummary: string | null = null

  const processLine = (line: string) => {
    if (!line.trim()) return
    let event: { type?: string; text?: string; summary?: string; message?: string }
    try {
      event = JSON.parse(line)
    } catch {
      throw new Error('The local LLM returned an invalid stream.')
    }
    if (event.type === 'delta' && typeof event.text === 'string') onDelta(event.text)
    else if (event.type === 'done' && typeof event.summary === 'string') completedSummary = event.summary
    else if (event.type === 'error') throw new Error(event.message ?? 'The local LLM isn’t available. Try again later.')
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) processLine(line)
    }
    buffer += decoder.decode()
    processLine(buffer)
  } catch (error) {
    await reader.cancel().catch(() => undefined)
    throw error
  }
  if (completedSummary === null) throw new Error('The local LLM stream ended before completion.')
  return { summary: completedSummary }
}

export async function fetchGoogleReviewSummary(placeId: string, confirm: boolean, key: string): Promise<GoogleReviewSummary> {
  return requestJson<GoogleReviewSummary>(`/restaurants/${encodeURIComponent(placeId)}/insights/google-review-summary`, {
    method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ confirm_cost: confirm })
  })
}

export async function getReviews(
  placeId: string,
  rating?: number | null,
  sort: ReviewSort = 'recent', pageSize = 20, cursor?: string | null
): Promise<ReviewListResponse> {
  const params = new URLSearchParams({ sort, page_size: String(pageSize) })
  if (rating) params.set('rating', String(rating))
  if (cursor) params.set('cursor', cursor)
  return requestJson<ReviewListResponse>(`/restaurants/${encodeURIComponent(placeId)}/reviews?${params.toString()}`)
}

export async function getLoadMoreOptions(placeId: string): Promise<LoadMoreOptions> {
  return requestJson<LoadMoreOptions>(`/restaurants/${encodeURIComponent(placeId)}/reviews/load-more/options`)
}

export async function loadMoreReviews(placeId: string, target: 20 | 50 | 100, restart: boolean, confirm: boolean, key: string): Promise<ProviderOperation> {
  return requestJson<ProviderOperation>(`/restaurants/${encodeURIComponent(placeId)}/reviews/load-more`, {
    method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ additional_target_count: target, restart_from_newest: restart, confirm_cost: confirm })
  })
}

export async function syncReviews(placeId: string, confirmCost: boolean, idempotencyKey: string): Promise<ReviewSyncResponse | ProviderOperation> {
  return requestJson<ReviewSyncResponse | ProviderOperation>(`/restaurants/${encodeURIComponent(placeId)}/reviews/sync`, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ confirm_cost: confirmCost })
  })
}

export async function checkForNewReviews(placeId: string, confirmCost: boolean, idempotencyKey: string): Promise<ReviewSyncResponse | ProviderOperation> {
  return requestJson<ReviewSyncResponse | ProviderOperation>(`/restaurants/${encodeURIComponent(placeId)}/reviews/check-new`, {
    method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify({ confirm_cost: confirmCost, force: true })
  })
}

export async function refreshReviews(placeId: string, confirmCost: boolean, idempotencyKey: string): Promise<ReviewSyncResponse | ProviderOperation> {
  return requestJson<ReviewSyncResponse | ProviderOperation>(`/restaurants/${encodeURIComponent(placeId)}/reviews/refresh`, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ confirm_cost: confirmCost, force: true })
  })
}

export async function getReviewFilterOptions(): Promise<ReviewFilterOptionsResponse> {
  return requestJson<ReviewFilterOptionsResponse>('/reviews/filter-options')
}

export async function filterReviews(
  placeId: string,
  controls: {
    rating?: number | null
    reviewer_label?: string | null
    content_filter?: string | null
    sort: ReviewSort
  }
): Promise<ReviewFilterResponse> {
  return requestJson<ReviewFilterResponse>(`/restaurants/${encodeURIComponent(placeId)}/reviews/filter`, {
    method: 'POST',
    body: JSON.stringify(controls)
  })
}

export async function getReviewerContext(reviewerId: string, reviewId: string): Promise<ReviewerContext> {
  return requestJson<ReviewerContext>(`/reviewers/${encodeURIComponent(reviewerId)}?current_review_id=${encodeURIComponent(reviewId)}`)
}

export async function getReviewerComparison(reviewerId: string, reviewId: string, timeWindow: string, matchLevel: string): Promise<ReviewerContext['comparison']> {
  return requestJson<ReviewerContext['comparison']>(`/reviewers/${encodeURIComponent(reviewerId)}/comparison?current_review_id=${encodeURIComponent(reviewId)}&time_window=${timeWindow}&match_level=${matchLevel}`)
}

export async function startReviewerContext(reviewerId: string, reviewId: string, confirm: boolean, force: boolean, key: string): Promise<ReviewerContext | ProviderOperation> {
  return requestJson<ReviewerContext | ProviderOperation>(`/reviewers/${encodeURIComponent(reviewerId)}/context`, { method: 'POST', headers: { 'Idempotency-Key': key }, body: JSON.stringify({ current_review_id: reviewId, confirm_cost: confirm, force_refresh: force }) })
}

export async function deleteReviewerContext(reviewerId: string): Promise<{ contributor_only_reviews_removed: number; observed_places_removed: number; restaurant_confirmed_reviews_preserved: number }> {
  return requestJson(`/reviewers/${encodeURIComponent(reviewerId)}/context`, { method: 'DELETE' })
}

export async function getProviderOperation(operationId: string): Promise<ProviderOperation> {
  return requestJson<ProviderOperation>(`/provider-operations/${encodeURIComponent(operationId)}`)
}

export async function getProviderOperations(): Promise<ProviderOperation[]> {
  const response = await requestJson<{ operations: ProviderOperation[] }>('/provider-operations?limit=20')
  return response.operations
}

export async function cancelProviderOperation(operationId: string): Promise<ProviderOperation> {
  return requestJson<ProviderOperation>(`/provider-operations/${encodeURIComponent(operationId)}/cancel`, {
    method: 'POST'
  })
}

export function newIdempotencyKey(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }

  // randomUUID is restricted to secure contexts, while getRandomValues remains
  // available for private-network HTTP deployments such as Tailscale IPs.
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0'))
  return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10).join('')}`
}

export async function getProviderUsage(): Promise<ProviderUsage[]> {
  const response = await requestJson<{ usage: ProviderUsage[] }>('/providers/usage')
  return response.usage
}
