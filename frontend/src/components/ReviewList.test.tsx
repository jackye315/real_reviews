import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import { ReviewList } from './ReviewList'

it('uses repeated decorative stars only for a valid overall review rating', () => {
  render(
    <ReviewList
      loading={false}
      total={1}
      filteredTotal={1}
      exactRating=""
      reviews={[{
        id: 'review-1', rating: 4, text: 'Great dinner.', original_text: null,
        publication_timestamp: null, last_edit_timestamp: null, canonical_source_url: null,
        author_display_name: null, author_avatar_url: null, source_labels: [],
        details: { food: 3 }, translated_details: {}, images: [],
        first_fetched_at: new Date(0).toISOString(), last_seen_at: new Date(0).toISOString(), suspected_duplicate: false
      }]}
    />
  )
  expect(screen.getByLabelText('4 out of 5 stars')).toHaveTextContent('4 ★★★★')
  expect(screen.queryByLabelText('3 out of 5 stars')).not.toBeInTheDocument()
  expect(screen.getByText('3')).toBeInTheDocument()
  expect(screen.getByRole('article')).toHaveClass('p-3.5')
  expect(screen.getByText('Great dinner.')).toHaveClass('mt-2', 'leading-6')
})
