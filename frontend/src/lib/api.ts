import type {
  PlaceResponse,
  ProviderUsage,
  RestaurantSearchPage,
  RestaurantSearchResult,
  Review,
  ReviewListResponse,
  ReviewSyncResponse
} from '../types/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
    ...options
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const message = payload?.detail?.message ?? payload?.detail ?? response.statusText
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

export async function getReviews(placeId: string): Promise<ReviewListResponse> {
  return requestJson<ReviewListResponse>(`/restaurants/${encodeURIComponent(placeId)}/reviews`)
}

export async function syncReviews(placeId: string, confirmCost = false): Promise<ReviewSyncResponse> {
  return requestJson<ReviewSyncResponse>(`/restaurants/${encodeURIComponent(placeId)}/reviews/sync`, {
    method: 'POST',
    body: JSON.stringify({ confirm_cost: confirmCost })
  })
}

export async function refreshReviews(placeId: string, confirmCost = false): Promise<ReviewSyncResponse> {
  return requestJson<ReviewSyncResponse>(`/restaurants/${encodeURIComponent(placeId)}/reviews/refresh`, {
    method: 'POST',
    body: JSON.stringify({ confirm_cost: confirmCost, force: true })
  })
}

export async function filterReviews(filterText: string, reviews: Review[]): Promise<string[]> {
  const response = await requestJson<{ selected_review_ids: string[] }>('/reviews/filter', {
    method: 'POST',
    body: JSON.stringify({
      filter_text: filterText,
      reviews: reviews.map((review) => ({
        id: review.id,
        text: review.text ?? review.original_text ?? '',
        rating: review.rating,
        publication_date: review.publication_timestamp
      }))
    })
  })
  return response.selected_review_ids
}

export async function getProviderUsage(): Promise<ProviderUsage[]> {
  const response = await requestJson<{ usage: ProviderUsage[] }>('/providers/usage')
  return response.usage
}
