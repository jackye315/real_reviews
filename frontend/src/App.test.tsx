import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './lib/api'
import type { PlaceResponse, RestaurantSearchResult, Review, ReviewerComparison } from './types/api'

vi.mock('./components/Autocomplete', () => ({
  Autocomplete: ({ onSelected }: { onSelected: (selection: unknown) => void }) => (
    <button
      type="button"
      onClick={() =>
        onSelected({
          google_place_id: 'auto-place',
          display_name: 'Autocomplete Cafe',
          formatted_address: '1 Auto St',
          place_types: ['restaurant'],
          google_maps_url: 'https://maps.example/auto'
        })
      }
    >
      Mock autocomplete select
    </button>
  )
}))

vi.mock('./lib/api', () => ({
  cancelProviderOperation: vi.fn(),
  checkForNewReviews: vi.fn(),
  filterReviews: vi.fn(),
  getLoadMoreOptions: vi.fn(),
  getProviderOperation: vi.fn(),
  getProviderOperations: vi.fn(),
  getProviderUsage: vi.fn(),
  getReviewFilterOptions: vi.fn(),
  getRestaurantDetail: vi.fn(),
  getReviewerComparison: vi.fn(),
  getReviewerContext: vi.fn(),
  getReviews: vi.fn(),
  loadMoreReviews: vi.fn(),
  startReviewerContext: vi.fn(),
  deleteReviewerContext: vi.fn(),
  persistSearchResult: vi.fn(),
  persistSelection: vi.fn(),
  newIdempotencyKey: vi.fn(() => 'test-idempotency-key'),
  refreshReviews: vi.fn(),
  searchRestaurants: vi.fn(),
  syncReviews: vi.fn()
}))

const place = (id: string, name: string): PlaceResponse => ({
  id: `${id}-uuid`,
  google_place_id: id,
  display_name: name,
  formatted_address: `${name} Address`,
  latitude: 40,
  longitude: -73,
  viewport: null,
  place_types: ['restaurant'],
  google_maps_url: `https://maps.example/${id}`,
  created_at: new Date(0).toISOString(),
  updated_at: new Date(0).toISOString()
})

const review = (): Review => ({
  id: 'review-1',
  rating: 5,
  text: 'Great outdoor seating.',
  original_text: null,
  publication_timestamp: new Date(0).toISOString(),
  last_edit_timestamp: null,
  canonical_source_url: null,
  author_display_name: 'Reviewer',
  author_avatar_url: null,
  reviewer_id: 'reviewer-1',
  source_labels: ['Google'],
  details: {},
  translated_details: {},
  images: [],
  first_fetched_at: new Date(0).toISOString(),
  last_seen_at: new Date(0).toISOString(),
  suspected_duplicate: false
})

const result = (id: string, name: string): RestaurantSearchResult => ({
  google_place_id: id,
  display_name: name,
  formatted_address: `${name} Address`,
  latitude: 40,
  longitude: -73,
  viewport: null,
  place_types: ['restaurant'],
  google_maps_url: `https://maps.example/${id}`,
  rating: 4.5,
  user_rating_count: 123,
  distance_meters: 804
})

const reviewerComparison = (
  matchLevel: ReviewerComparison['match_level'],
  timeWindow: ReviewerComparison['time_window'],
  sampleSize: number
): ReviewerComparison => ({
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
  contains_approximate_dates: true
})

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  )
}

beforeEach(() => {
  window.history.replaceState({}, '', '/')
  vi.mocked(api.searchRestaurants).mockResolvedValue({
    results: [result('place-1', 'First Noodles'), result('place-2', 'Second Sushi')],
    next_page_token: 'next-page'
  })
  vi.mocked(api.persistSearchResult).mockImplementation(async (item) => place(item.google_place_id, item.display_name))
  vi.mocked(api.persistSelection).mockResolvedValue(place('auto-place', 'Autocomplete Cafe'))
  vi.mocked(api.getReviews).mockResolvedValue({ reviews: [], total: 0, filtered_total: 0, topics: [], topics_fetched_at: null })
  vi.mocked(api.getReviewerContext).mockResolvedValue({ reviewer: { id: 'reviewer-1', display_name: 'Reviewer', context_generation: 0, context_status: 'not_loaded' }, current: { review: review(), restaurant_name: 'First Noodles', restaurant_place_id: 'place-1', normalized_venue_type: 'restaurant', comparison_family: 'restaurant' }, comparison: null, broader_comparison: null, active_operation_id: null, stale: false })
  vi.mocked(api.getProviderOperations).mockResolvedValue([])
  vi.mocked(api.getLoadMoreOptions).mockResolvedValue({ cursor_available: false, remaining_effective_budget: 225, choices: [] })
  vi.mocked(api.getReviewFilterOptions).mockResolvedValue({
    reviewer_label_options: [
      { value: 'chinese', label: 'Chinese' },
      { value: 'korean', label: 'Korean' },
      { value: 'japanese', label: 'Japanese' },
      { value: 'american', label: 'American' },
      { value: 'italian', label: 'Italian' }
    ]
  })
  vi.mocked(api.filterReviews).mockResolvedValue({
    reviews: [review()],
    total: 1,
    candidate_count: 1,
    filtered_total: 1,
    selected_review_ids: ['review-1'],
    skipped_missing_label_count: 0,
    rating_filter: null,
    reviewer_label_filter: null,
    content_filter: 'outdoor seating',
    sort: 'recent',
    llm_used: true,
    topics: [],
    topics_fetched_at: null
  })
  vi.mocked(api.getProviderUsage).mockResolvedValue([
    {
      id: 'usage-1',
      provider: 'serpapi',
      plan_period: '2026-07',
      successful_request_count: 2,
      cached_response_count: 0,
      failed_request_count: 1,
      updated_at: new Date(0).toISOString()
    }
  ])
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => setTimeout(callback, 0))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('App split workspace', () => {
  it('starts on focused landing without querying provider usage', () => {
    renderApp()
    expect(screen.getByRole('heading', { name: /find a restaurant/i })).toBeInTheDocument()
    expect(screen.queryByText(/provider usage/i)).not.toBeInTheDocument()
    expect(api.getProviderUsage).not.toHaveBeenCalled()
  })

  it('transitions from free-form search into split workspace results', async () => {
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))

    expect(await screen.findByText('First Noodles')).toBeInTheDocument()
    expect(screen.getByText(/select a restaurant/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /load next search page/i })).toBeInTheDocument()
  })

  it('opens selected result in the reviews pane without clearing result rows', async () => {
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))

    expect(await screen.findByRole('heading', { name: 'First Noodles' })).toBeInTheDocument()
    expect(screen.getByText('Second Sushi')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Second Sushi'))
    expect(await screen.findByRole('heading', { name: 'Second Sushi' })).toBeInTheDocument()
    expect(screen.getByText('First Noodles')).toBeInTheDocument()
  })

  it('renders stored provider topics only after reviews exist and applies topic text locally', async () => {
    vi.mocked(api.getReviews).mockResolvedValueOnce({
      reviews: [review()],
      total: 1,
      filtered_total: 1,
      topics: [{ provider_topic_id: '/m/outdoor', keyword: 'outdoor seating', mentions: 24, language_code: 'en', rank: 0 }],
      topics_fetched_at: new Date(0).toISOString()
    })
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))

    expect(await screen.findByText(/mentioned in reviews/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /outdoor seating \(24\)/i }))
    expect(screen.getByPlaceholderText(/mentions spicy noodles/i)).toHaveValue('outdoor seating')
    await waitFor(() => expect(api.filterReviews).toHaveBeenCalledWith('place-1', expect.objectContaining({ content_filter: 'outdoor seating', sort: 'recent' })))
  })

  it('shows visible progress and a concrete summary for a review refresh', async () => {
    vi.mocked(api.getReviews).mockResolvedValue({
      reviews: [review()],
      total: 1,
      filtered_total: 1,
      topics: [],
      topics_fetched_at: null
    })
    let finishRefresh: ((value: Awaited<ReturnType<typeof api.refreshReviews>>) => void) | undefined
    vi.mocked(api.refreshReviews).mockImplementation(
      () => new Promise((resolve) => {
        finishRefresh = resolve
      })
    )
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))

    await screen.findByText('Great outdoor seating.')
    fireEvent.click(screen.getByRole('button', { name: /^refresh relevance$/i }))
    expect(await screen.findByText(/refreshing relevance from serpapi/i)).toBeInTheDocument()

    finishRefresh?.({
      place_id: 'place-1',
      status: 'completed',
      collected_unique_count: 2,
      successful_request_count: 1,
      pagination_cursor: null,
      stop_reason: 'known_unchanged_streak',
      reviews: [review()],
      topics: [{ provider_topic_id: '/m/food', keyword: 'food', mentions: 3, language_code: 'en', rank: 0 }],
      topics_fetched_at: new Date(0).toISOString(),
      fallback_used: false,
      message: null
    })

    expect(await screen.findByText(/refresh completed: 2 new review\(s\), 1 stored review\(s\), and 1 upstream request\(s\)/i)).toBeInTheDocument()
  })

  it('shows refresh failures in the restaurant review pane', async () => {
    vi.mocked(api.getReviews).mockResolvedValue({
      reviews: [review()],
      total: 1,
      filtered_total: 1,
      topics: [],
      topics_fetched_at: null
    })
    vi.mocked(api.refreshReviews).mockRejectedValueOnce(new Error('Internal Server Error'))
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))

    await screen.findByText('Great outdoor seating.')
    fireEvent.click(screen.getByRole('button', { name: /^refresh relevance$/i }))

    expect(await screen.findByText(/refresh failed: internal server error/i)).toBeInTheDocument()
  })

  it('refetches stored reviews for exact rating and sort controls and reset restores defaults', async () => {
    vi.mocked(api.getReviews).mockResolvedValue({
      reviews: [review()],
      total: 2,
      filtered_total: 1,
      topics: [],
      topics_fetched_at: null
    })
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))

    await screen.findByLabelText(/exact rating/i)
    expect(screen.getByText(/1 of 2 reviews/i)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/exact rating/i), { target: { value: '4' } })
    await waitFor(() => expect(api.getReviews).toHaveBeenCalledWith('place-1', 4, 'recent', 20, null))

    expect(await screen.findByLabelText(/reviewer label/i)).toHaveDisplayValue('Any reviewer label')
    const reviewSortSelect = await screen.findByLabelText(/review sort/i)
    expect(within(reviewSortSelect).queryByRole('option', { name: 'Most relevant' })).not.toBeInTheDocument()
    expect(screen.getByText('Relevance not fetched')).toBeInTheDocument()
    fireEvent.change(reviewSortSelect, { target: { value: 'rating_high' } })
    await waitFor(() => expect(api.getReviews).toHaveBeenCalledWith('place-1', 4, 'rating_high', 20, null))

    fireEvent.click(await screen.findByRole('button', { name: /reset/i }))
    await waitFor(() => expect(api.getReviews).toHaveBeenCalledWith('place-1', null, 'recent', 20, null))
  })

  it('shows a concise most-relevant sort only when a relevance snapshot exists', async () => {
    vi.mocked(api.getReviews).mockResolvedValue({
      reviews: [review()],
      total: 1,
      filtered_total: 1,
      relevance_available: true,
      relevance_status: 'complete',
      relevance_ranked_count: 1,
      topics: [],
      topics_fetched_at: null
    })
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))

    const reviewSortSelect = await screen.findByLabelText(/review sort/i)
    expect(within(reviewSortSelect).getByRole('option', { name: 'Most relevant' })).toBeInTheDocument()
    await waitFor(() => expect(reviewSortSelect).toHaveDisplayValue('Most relevant'))
  })

  it('loads reviewer-label options from backend and submits unified label filter', async () => {
    vi.mocked(api.getReviews).mockResolvedValue({
      reviews: [review()],
      total: 1,
      filtered_total: 1,
      topics: [],
      topics_fetched_at: null
    })
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))

    const reviewerSelect = await screen.findByLabelText(/reviewer label/i)
    await screen.findByRole('option', { name: 'Jack' })
    expect(api.getReviewFilterOptions).toHaveBeenCalled()
    fireEvent.change(reviewerSelect, { target: { value: 'jack' } })

    await waitFor(() => expect(api.filterReviews).toHaveBeenCalledWith('place-1', expect.objectContaining({
      reviewer_label: 'jack',
      content_filter: null,
      sort: 'recent'
    })))
  })

  it('keeps deterministic reviews visible when semantic filtering fails', async () => {
    vi.mocked(api.getReviews).mockResolvedValue({
      reviews: [review()],
      total: 1,
      filtered_total: 1,
      topics: [],
      topics_fetched_at: null
    })
    vi.mocked(api.filterReviews).mockRejectedValueOnce(new Error('LLM timeout'))
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))

    expect(await screen.findByText('Great outdoor seating.')).toBeInTheDocument()
    fireEvent.change(screen.getByPlaceholderText(/mentions spicy noodles/i), { target: { value: 'patio' } })
    fireEvent.click(screen.getByRole('button', { name: /^filter$/i }))

    expect(await screen.findByText(/couldn’t apply the new filter/i)).toBeInTheDocument()
    expect(screen.getByText('Great outdoor seating.')).toBeInTheDocument()
  })

  it('opens direct autocomplete selection in the review workspace', async () => {
    renderApp()
    fireEvent.click(screen.getByRole('button', { name: /mock autocomplete select/i }))
    expect(await screen.findByRole('heading', { name: 'Autocomplete Cafe' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /results/i })).toBeInTheDocument()
  })

  it('queries provider usage lazily from the developer drawer', async () => {
    renderApp()
    expect(api.getProviderUsage).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /developer/i }))
    const dialog = await screen.findByRole('dialog', { name: /provider usage/i })
    expect(await within(dialog).findByText('serpapi')).toBeInTheDocument()
    expect(api.getProviderUsage).toHaveBeenCalledTimes(1)
  })

  it('keeps the workspace and restaurant header while reviewer context replaces only reviews', async () => {
    vi.mocked(api.getReviews).mockResolvedValue({ reviews: [review()], total: 1, filtered_total: 1, topics: [], topics_fetched_at: null })
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))
    fireEvent.click(await screen.findByRole('button', { name: /reviewer/i }))
    expect(await screen.findByRole('heading', { name: 'Reviewer' })).toBeInTheDocument()
    expect(screen.getByText('Second Sushi')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'First Noodles' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /open filters/i })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /back to reviews/i }))
    expect(await screen.findByText('Great outdoor seating.')).toBeInTheDocument()
  })

  it('requests exact and broader comparisons for the same changed time window', async () => {
    const exactTwoYears = reviewerComparison('exact_type', 'two_years', 0)
    const broaderTwoYears = reviewerComparison('comparison_family', 'two_years', 15)
    vi.mocked(api.getReviews).mockResolvedValue({ reviews: [review()], total: 1, filtered_total: 1, topics: [], topics_fetched_at: null })
    vi.mocked(api.getReviewerContext).mockResolvedValue({
      reviewer: {
        id: 'reviewer-1',
        display_name: 'Reviewer',
        context_generation: 1,
        context_status: 'available',
        provider_results_returned: 50,
        accepted_food_and_drink_count: 29
      },
      current: {
        review: { ...review(), rating: 2 },
        restaurant_name: 'First Noodles',
        restaurant_place_id: 'place-1',
        normalized_venue_type: 'tibetan_restaurant',
        comparison_family: 'restaurant'
      },
      comparison: exactTwoYears,
      broader_comparison: broaderTwoYears,
      active_operation_id: null,
      stale: false
    })
    vi.mocked(api.getReviewerComparison).mockImplementation(
      async (_reviewerId, _reviewId, timeWindow, matchLevel) =>
        reviewerComparison(
          matchLevel as ReviewerComparison['match_level'],
          timeWindow as ReviewerComparison['time_window'],
          matchLevel === 'exact_type' ? 0 : 8
        )
    )

    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'noodles' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))
    fireEvent.click(await screen.findByRole('button', { name: /reviewer/i }))
    fireEvent.change(await screen.findByLabelText(/window/i), { target: { value: 'one_year' } })

    await waitFor(() => {
      expect(api.getReviewerComparison).toHaveBeenCalledWith(
        'reviewer-1',
        'review-1',
        'one_year',
        'exact_type'
      )
      expect(api.getReviewerComparison).toHaveBeenCalledWith(
        'reviewer-1',
        'review-1',
        'one_year',
        'comparison_family'
      )
    })
  })

  it('supports mobile-style back navigation from search-result reviews to preserved results', async () => {
    renderApp()
    fireEvent.change(screen.getByLabelText(/free-form restaurant search/i), { target: { value: 'sushi' } })
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    fireEvent.click(await screen.findByText('First Noodles'))
    fireEvent.click(await screen.findByRole('button', { name: /results/i }))
    expect(await screen.findByText('Second Sushi')).toBeInTheDocument()
  })
})
