import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Review, ReviewerComparison, ReviewerContext, ReviewerRelevantReview } from '../types/api'
import { ReviewerPane } from './ReviewerPane'

afterEach(cleanup)

const currentReview: Review = {
  id: 'review-current',
  rating: 2,
  text: 'Synthetic current review.',
  original_text: null,
  publication_timestamp: new Date(0).toISOString(),
  last_edit_timestamp: null,
  canonical_source_url: null,
  author_display_name: 'Synthetic reviewer',
  author_avatar_url: null,
  reviewer_id: 'reviewer-1',
  source_labels: ['Google'],
  details: {},
  translated_details: {},
  images: [],
  first_fetched_at: new Date(0).toISOString(),
  last_seen_at: new Date(0).toISOString(),
  suspected_duplicate: false
}

const relevantReviews: ReviewerRelevantReview[] = Array.from({ length: 6 }, (_, index) => ({
  id: `other-review-${index + 1}`,
  place_name: `Other restaurant ${index + 1}`,
  rating: index === 5 ? 4 : 5,
  text: index === 0
    ? `Visible stored review text ${'with enough detail to require expansion. '.repeat(12)}`
    : `Stored review text ${index + 1}`,
  original_text: null,
  provider_date_text: `${index + 1} months ago`,
  publication_date_is_approximate: true,
  source_url: `https://reviews.example/${index + 1}`
}))

function comparison(
  matchLevel: ReviewerComparison['match_level'],
  sampleSize: number,
  reviews: ReviewerRelevantReview[] = []
): ReviewerComparison {
  return {
    current_rating: 2,
    match_level: matchLevel,
    normalized_venue_type: 'tibetan_restaurant',
    comparison_family: 'restaurant',
    time_window: 'two_years',
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
    relevant_reviews: reviews
  }
}

const context: ReviewerContext = {
  reviewer: {
    id: 'reviewer-1',
    display_name: 'Synthetic reviewer',
    context_status: 'available',
    context_generation: 1,
    provider_results_returned: 50,
    accepted_food_and_drink_count: 29
  },
  current: {
    review: currentReview,
    restaurant_name: 'Synthetic Tibetan Restaurant',
    restaurant_place_id: 'place-1',
    normalized_venue_type: 'tibetan_restaurant',
    comparison_family: 'restaurant'
  },
  comparison: comparison('exact_type', 0),
  broader_comparison: comparison('comparison_family', 15, relevantReviews),
  active_operation_id: null,
  stale: false
}

describe('ReviewerPane comparison fallback', () => {
  it('shows non-empty broader history when the exact-type sample is empty', () => {
    render(
      <ReviewerPane
        context={context}
        loading={false}
        error={null}
        onBack={vi.fn()}
        timeWindow="two_years"
        onTimeWindowChange={vi.fn()}
        onAnalyze={vi.fn()}
        onRefresh={vi.fn()}
        onDelete={vi.fn()}
      />
    )

    expect(screen.getByText(/no other tibetan restaurant reviews observed/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /broader restaurant comparison/i })).toBeInTheDocument()
    expect(screen.getByText(/15 other (restaurants|venues)/i)).toBeInTheDocument()
    expect(screen.getByText(/4\.7 stars/i)).toBeInTheDocument()

    const exactSummary = screen.getByRole('region', { name: /other tibetan restaurants rating summary/i })
    const broaderSummary = screen.getByRole('region', { name: /broader restaurants rating summary/i })
    expect(within(exactSummary).getByText(/no other matching reviews/i)).toBeInTheDocument()
    expect(within(broaderSummary).getByText(/4\.7 stars/i)).toBeInTheDocument()
    expect(within(broaderSummary).getByText(/5\.0 stars/i)).toBeInTheDocument()
    expect(within(broaderSummary).getByText('1.00')).toBeInTheDocument()
    expect(within(broaderSummary).getByLabelText(/rating distribution/i)).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: /broader restaurant comparison/i })).queryByText('Average')).not.toBeInTheDocument()
  })

  it('renders stored review bodies progressively inside aligned section cards', () => {
    render(
      <ReviewerPane
        context={context}
        loading={false}
        error={null}
        onBack={vi.fn()}
        timeWindow="two_years"
        onTimeWindowChange={vi.fn()}
        onAnalyze={vi.fn()}
        onRefresh={vi.fn()}
        onDelete={vi.fn()}
      />
    )

    const originalCard = screen.getByRole('region', { name: /synthetic tibetan restaurant/i })
    const exactCard = screen.getByRole('region', { name: /exact tibetan restaurant comparison/i })
    const broaderCard = screen.getByRole('region', { name: /broader restaurant comparison/i })
    for (const card of [originalCard, exactCard, broaderCard]) {
      expect(card).toHaveClass('rounded-2xl', 'border', 'p-4')
    }

    expect(screen.getByText(/visible stored review text/i)).toBeInTheDocument()
    expect(screen.getByText('Stored review text 5')).toBeInTheDocument()
    expect(screen.queryByText('Stored review text 6')).not.toBeInTheDocument()
    expect(screen.getByText(/showing 5 of 15/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /show all 6 reviews/i }))
    expect(screen.getByText('Stored review text 6')).toBeInTheDocument()
    expect(screen.getByText(/showing 6 of 15/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /show full review/i }))
    expect(screen.getByRole('button', { name: /show less/i })).toHaveAttribute('aria-expanded', 'true')
  })
})
