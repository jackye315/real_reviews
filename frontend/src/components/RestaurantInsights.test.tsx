import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { RestaurantInsights } from './RestaurantInsights'
import * as api from '../lib/api'
import type { Review } from '../types/api'

vi.mock('../lib/api', () => ({
  streamDishSummary: vi.fn()
}))

const review = (id: string, text: string): Review => ({
  id, text, original_text: null, rating: 5, publication_timestamp: null, last_edit_timestamp: null,
  canonical_source_url: null, author_display_name: null, author_avatar_url: null, reviewer_id: null,
  source_labels: ['Google'], details: {}, translated_details: {}, images: [], first_fetched_at: '', last_seen_at: '', suspected_duplicate: false
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('RestaurantInsights', () => {
  it('submits only the first currently loaded reviews in visible order and replaces the saved paragraph', async () => {
    vi.mocked(api.streamDishSummary).mockImplementation(async (_placeId, _texts, onDelta) => {
      onDelta('Reviewers often ')
      onDelta('praise the momos.')
      return { summary: 'Reviewers often praise the momos.' }
    })
    render(<RestaurantInsights placeId="place-1" initialDishSummary="Older summary." visibleReviews={[review('1', 'first'), review('2', 'second')]} />)

    fireEvent.change(screen.getByLabelText(/reviews to include/i), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: /replace summary/i }))

    await waitFor(() => expect(api.streamDishSummary).toHaveBeenCalledWith('place-1', ['first', 'second'], expect.any(Function)))
    expect(await screen.findByText('Reviewers often praise the momos.')).toBeInTheDocument()
    expect(screen.queryByText('Older summary.')).not.toBeInTheDocument()
  })

  it('uses every currently displayed review when the requested count is larger', async () => {
    vi.mocked(api.streamDishSummary).mockResolvedValue({ summary: 'Summary from one review.' })
    render(<RestaurantInsights placeId="place-1" visibleReviews={[review('1', 'first')]} />)
    fireEvent.change(screen.getByLabelText(/reviews to include/i), { target: { value: '50' } })
    fireEvent.click(screen.getByRole('button', { name: /generate summary/i }))

    await waitFor(() => expect(api.streamDishSummary).toHaveBeenCalledWith('place-1', ['first'], expect.any(Function)))
    expect(await screen.findByText('Summary from one review.')).toBeInTheDocument()
    expect(screen.queryByText(/only 1 loaded review/i)).not.toBeInTheDocument()
  })

  it('restores the previous paragraph when a stream fails after provisional text', async () => {
    vi.mocked(api.streamDishSummary).mockImplementation(async (_placeId, _texts, onDelta) => {
      onDelta('Provisional replacement')
      throw new Error('The local LLM stream failed.')
    })
    render(<RestaurantInsights placeId="place-1" initialDishSummary="Older summary." visibleReviews={[review('1', 'first')]} />)

    fireEvent.change(screen.getByLabelText(/reviews to include/i), { target: { value: '1' } })
    fireEvent.click(screen.getByRole('button', { name: /replace summary/i }))

    expect(await screen.findByText('The local LLM stream failed.')).toBeInTheDocument()
    expect(screen.getByText('Older summary.')).toBeInTheDocument()
    expect(screen.queryByText('Provisional replacement')).not.toBeInTheDocument()
  })

  it('does not expose the dormant Google review-summary action', () => {
    render(<RestaurantInsights placeId="place-1" visibleReviews={[]} />)
    expect(screen.queryByRole('button', { name: /google review summary/i })).not.toBeInTheDocument()
  })
})
