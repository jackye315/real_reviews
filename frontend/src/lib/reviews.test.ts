import { describe, expect, it } from 'vitest'
import { filterByMinimumRating } from './reviews'
import type { Review } from '../types/api'

function review(id: string, rating: number | null): Review {
  return {
    id,
    rating,
    text: null,
    original_text: null,
    publication_timestamp: null,
    last_edit_timestamp: null,
    canonical_source_url: null,
    author_display_name: null,
    author_avatar_url: null,
    source_labels: [],
    details: {},
    translated_details: {},
    images: [],
    first_fetched_at: new Date(0).toISOString(),
    last_seen_at: new Date(0).toISOString(),
    suspected_duplicate: false
  }
}

describe('filterByMinimumRating', () => {
  it('keeps reviews at or above the selected rating', () => {
    expect(filterByMinimumRating([review('a', 5), review('b', 3), review('c', null)], 4).map((item) => item.id)).toEqual(['a'])
  })
})
