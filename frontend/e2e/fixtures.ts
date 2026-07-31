import type { Page, Route } from '@playwright/test'

const firstResult = {
  google_place_id: 'place-1',
  display_name: 'First Noodles With A Surprisingly Long Mobile Name',
  formatted_address: '123 Very Long Address Avenue, Queens, NY 11111',
  google_maps_url: 'https://maps.example/place-1',
  latitude: 40.7,
  longitude: -73.9,
  viewport: null,
  place_types: ['restaurant'],
  rating: 4.5,
  user_rating_count: 123,
  distance_meters: 805
}

const secondResult = {
  ...firstResult,
  google_place_id: 'place-2',
  display_name: 'Second Sushi',
  formatted_address: '456 Compact Street, Queens, NY 11111',
  google_maps_url: 'https://maps.example/place-2'
}

const review = {
  id: 'review-1',
  rating: 5,
  text: 'Great outdoor seating with a long review body that should wrap naturally on small screens without creating horizontal overflow.',
  original_text: null,
  language_code: 'en',
  publication_timestamp: new Date(0).toISOString(),
  relative_time_description: 'long ago',
  author_display_name: 'Reviewer With A Long Display Name',
  canonical_source_url: 'https://reviews.example/original/review/with/a/very/long/path/that/must/wrap',
  source_labels: ['Google'],
  last_seen_at: new Date(0).toISOString(),
  first_seen_at: new Date(0).toISOString()
}

export async function mockApi(page: Page) {
  await page.route('**/maps/api/js**', (route) => route.abort())
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'POST' && path.endsWith('/restaurants/search')) {
      return json(route, { results: [firstResult, secondResult], next_page_token: 'next-page' })
    }

    if (method === 'POST' && path.endsWith('/restaurants/selection')) {
      const body = request.postDataJSON() as { google_place_id: string; display_name: string; formatted_address?: string; google_maps_url?: string }
      return json(route, {
        google_place_id: body.google_place_id,
        display_name: body.display_name,
        formatted_address: body.formatted_address ?? 'Saved Address',
        google_maps_url: body.google_maps_url ?? null,
        latitude: null,
        longitude: null,
        place_types: [],
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString()
      })
    }

    if (method === 'GET' && path.endsWith('/reviews/filter-options')) {
      return json(route, { reviewer_label_options: [{ value: 'jack', label: 'Jack' }] })
    }

    if (method === 'GET' && path.includes('/restaurants/place-1/reviews')) {
      return json(route, reviewList())
    }

    if (method === 'POST' && path.includes('/restaurants/place-1/reviews/filter')) {
      return json(route, {
        ...reviewList(),
        candidate_count: 1,
        selected_review_ids: ['review-1'],
        skipped_missing_label_count: 0,
        rating_filter: null,
        reviewer_label_filter: null,
        content_filter: 'outdoor seating',
        sort: 'recent',
        llm_used: true,
        message: null
      })
    }

    if (method === 'GET' && path.endsWith('/providers/usage')) {
      return json(route, { usage: [] })
    }

    return json(route, {}, 404)
  })
}

function reviewList() {
  return {
    reviews: [review],
    total: 1,
    filtered_total: 1,
    topics: [{ provider_topic_id: '/m/outdoor', keyword: 'outdoor seating', mentions: 24, language_code: 'en', rank: 0 }],
    topics_fetched_at: new Date(0).toISOString()
  }
}

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body)
  })
}
