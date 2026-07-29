import type { Review } from '../types/api'

export function filterByMinimumRating(reviews: Review[], minRating: number | null): Review[] {
  if (!minRating) return reviews
  return reviews.filter((review) => review.rating !== null && review.rating !== undefined && review.rating >= minRating)
}
