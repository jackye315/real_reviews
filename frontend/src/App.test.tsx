import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './lib/api'
import type { PlaceResponse, RestaurantSearchResult, Review } from './types/api'

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
  filterReviews: vi.fn(),
  getProviderUsage: vi.fn(),
  getReviews: vi.fn(),
  persistSearchResult: vi.fn(),
  persistSelection: vi.fn(),
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
  source_labels: ['Google'],
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

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  )
}

beforeEach(() => {
  vi.mocked(api.searchRestaurants).mockResolvedValue({
    results: [result('place-1', 'First Noodles'), result('place-2', 'Second Sushi')],
    next_page_token: 'next-page'
  })
  vi.mocked(api.persistSearchResult).mockImplementation(async (item) => place(item.google_place_id, item.display_name))
  vi.mocked(api.persistSelection).mockResolvedValue(place('auto-place', 'Autocomplete Cafe'))
  vi.mocked(api.getReviews).mockResolvedValue({ reviews: [], total: 0, topics: [], topics_fetched_at: null })
  vi.mocked(api.filterReviews).mockResolvedValue([])
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
    await waitFor(() => expect(api.filterReviews).toHaveBeenCalledWith('outdoor seating', expect.any(Array)))
  })

  it('opens direct autocomplete selection in the review workspace', async () => {
    renderApp()
    fireEvent.click(screen.getByRole('button', { name: /mock autocomplete select/i }))
    expect(await screen.findByRole('heading', { name: 'Autocomplete Cafe' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /back to results/i })).toBeInTheDocument()
  })

  it('queries provider usage lazily from the developer drawer', async () => {
    renderApp()
    expect(api.getProviderUsage).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: /developer/i }))
    const dialog = await screen.findByRole('dialog', { name: /provider usage/i })
    expect(await within(dialog).findByText('serpapi')).toBeInTheDocument()
    expect(api.getProviderUsage).toHaveBeenCalledTimes(1)
  })

  it('supports mobile-style back navigation from reviews to results', async () => {
    renderApp()
    fireEvent.click(screen.getByRole('button', { name: /mock autocomplete select/i }))
    fireEvent.click(await screen.findByRole('button', { name: /back to results/i }))
    expect(screen.getByText(/search results will appear here/i)).toBeInTheDocument()
  })
})
