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
  reviewer_id: 'reviewer-1',
  canonical_source_url: 'https://reviews.example/original/review/with/a/very/long/path/that/must/wrap',
  source_labels: ['Google'],
  details: {
    meal_type: 'Dinner',
    food: 5,
    service: 3,
    atmosphere: 4,
    recommended_dishes: ['Margherita pizza', 'Garlic knots'],
    accessibility: 'Step-free entrance and accessible seating'
  },
  translated_details: {},
  images: Array.from({ length: 7 }, (_, index) => ({
    url: `https://images.example/review-photo-${index + 1}.svg`,
    position: index,
    provider: 'serpapi'
  })),
  last_seen_at: new Date(0).toISOString(),
  first_seen_at: new Date(0).toISOString()
}

type ReviewerContextFixture = 'not_loaded' | 'exact_empty_broader'

export async function mockApi(
  page: Page,
  options: { reviewerContext?: ReviewerContextFixture } = {}
) {
  await page.route('**/maps/api/js**', (route) => route.abort())
  await page.route('**/review-photo-*.svg', (route) => route.fulfill({
    status: 200,
    contentType: 'image/svg+xml',
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="144" height="112"><rect width="144" height="112" fill="#DED8CE"/></svg>'
  }))
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

    if (method === 'GET' && path === '/api/v1/restaurants/place-1') {
      return json(route, { place: { ...firstResult, id: 'internal-place-1', created_at: new Date(0).toISOString(), updated_at: new Date(0).toISOString() }, stored_review_count: 1, last_fetch_time: null })
    }

    if (method === 'GET' && path.endsWith('/reviewers/reviewer-1/comparison')) {
      const matchLevel = url.searchParams.get('match_level') === 'comparison_family'
        ? 'comparison_family'
        : 'exact_type'
      const timeWindow = url.searchParams.get('time_window') ?? 'two_years'
      return json(route, reviewerComparison(matchLevel, timeWindow, matchLevel === 'exact_type' ? 0 : 15))
    }

    if (method === 'GET' && path.includes('/reviewers/reviewer-1')) {
      return json(route, reviewerContext(options.reviewerContext ?? 'not_loaded'))
    }

    if (method === 'GET' && path.endsWith('/reviews/filter-options')) {
      return json(route, { reviewer_label_options: [{ value: 'jack', label: 'Jack' }] })
    }

    if (method === 'GET' && path.endsWith('/reviews/load-more/options')) {
      return json(route, { cursor_available: true, active_operation_id: null, remaining_effective_budget: 12, choices: [{ provider_record_count: 20, estimated_request_count: 1, allowed: true }, { provider_record_count: 50, estimated_request_count: 3, allowed: true }, { provider_record_count: 100, estimated_request_count: 5, allowed: true }] })
    }

    if (method === 'GET' && path.includes('/restaurants/place-1/reviews')) {
      return json(route, reviewList(url.searchParams.get('cursor') === 'next' ? [secondReview] : [review], url.searchParams.get('cursor') ? null : 'next'))
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

const secondReview = { ...review, id: 'review-2', text: 'Older saved review.' }

function reviewerComparison(matchLevel: string, timeWindow: string, sampleSize: number) {
  return {
    current_rating: 2,
    match_level: matchLevel,
    normalized_venue_type: 'tibetan_restaurant',
    comparison_family: 'restaurant',
    time_window: timeWindow,
    sample_size: sampleSize,
    average_rating: sampleSize ? 4.7 : null,
    median_rating: sampleSize ? 5 : null,
    standard_deviation: sampleSize ? 1 : null,
    difference_from_average: sampleSize ? -2.7 : null,
    rating_distribution: sampleSize
      ? { '1': 1, '2': 0, '3': 0, '4': 1, '5': sampleSize - 2 }
      : { '1': 0, '2': 0, '3': 0, '4': 0, '5': 0 },
    individual_ratings: [],
    contains_approximate_dates: true,
    context_generation: 1,
    relevant_reviews: matchLevel === 'comparison_family'
      ? Array.from({ length: sampleSize }, (_, index) => ({
          id: `comparison-review-${index + 1}`,
          place_name: `Comparison restaurant ${index + 1}`,
          rating: index === sampleSize - 1 ? 1 : 5,
          text: index === 0
            ? 'This is the stored review text for the first comparison restaurant.'
            : `Stored comparison review text ${index + 1}.`,
          original_text: null,
          provider_date_text: `${index + 1} months ago`,
          publication_date_is_approximate: true,
          source_url: `https://reviews.example/comparison-${index + 1}`
        }))
      : []
  }
}

function reviewerContext(mode: ReviewerContextFixture) {
  if (mode === 'exact_empty_broader') {
    return {
      reviewer: {
        id: 'reviewer-1',
        display_name: 'Reviewer With A Long Display Name',
        local_guide: true,
        provider_review_count: 47,
        provider_photo_count: 21,
        provider_results_returned: 50,
        accepted_food_and_drink_count: 29,
        context_status: 'available',
        context_generation: 1,
        rating_distribution: {}
      },
      current: {
        review: { ...review, rating: 2 },
        restaurant_name: firstResult.display_name,
        restaurant_place_id: 'place-1',
        normalized_venue_type: 'tibetan_restaurant',
        comparison_family: 'restaurant'
      },
      comparison: reviewerComparison('exact_type', 'two_years', 0),
      broader_comparison: reviewerComparison('comparison_family', 'two_years', 15),
      active_operation_id: null,
      stale: false
    }
  }
  return {
    reviewer: { id: 'reviewer-1', display_name: 'Reviewer With A Long Display Name', local_guide: true, provider_review_count: 1031, provider_photo_count: 12, context_status: 'not_loaded', context_generation: 0, rating_distribution: {} },
    current: { review, restaurant_name: firstResult.display_name, restaurant_place_id: 'place-1', normalized_venue_type: 'restaurant', comparison_family: 'restaurant' },
    comparison: null, broader_comparison: null, active_operation_id: null, stale: false
  }
}

function reviewList(reviews = [review], next_cursor: string | null = null) {
  return {
    reviews,
    page_size: 20,
    next_cursor,
    has_more: Boolean(next_cursor),
    review_corpus_version: 1,
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
