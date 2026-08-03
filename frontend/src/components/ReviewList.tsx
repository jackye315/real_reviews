import type { Review } from '../types/api'
import { ReviewRichData } from './ReviewRichData'

function OverallRating({ rating }: { rating: number | null | undefined }) {
  if (typeof rating === 'number' && Number.isInteger(rating) && rating >= 1 && rating <= 5) {
    return <span className="font-semibold text-[#E3A333]" aria-label={`${rating} out of 5 stars`}><span aria-hidden="true">{rating} {'★'.repeat(rating)}</span></span>
  }
  return <span className="font-semibold text-[#E3A333]">{rating ?? 'No rating'}</span>
}

export function ReviewList({
  reviews,
  loading,
  total,
  filteredTotal,
  exactRating,
  onOpenReviewer
}: {
  reviews: Review[]
  loading: boolean
  total: number
  filteredTotal: number
  exactRating: string
  onOpenReviewer?: (reviewerId: string, reviewId: string, source: HTMLButtonElement) => void
}) {
  if (loading) return <p className="text-[#6B7378]">Loading stored reviews…</p>
  if (!total) return <p className="text-[#6B7378]">No stored reviews yet. Fetch reviews to load topics and review filtering controls.</p>
  if (!filteredTotal) return <p className="text-[#6B7378]">No stored reviews match {exactRating ? `${exactRating} stars` : 'the current filters'}.</p>
  if (!reviews.length) return <p className="text-[#6B7378]">No reviews match the active content filter.</p>
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {reviews.map((review) => (
        <article key={review.id} className="min-w-0 rounded-2xl border border-[#DED8CE] bg-[#FFFDFC] p-3.5">
          <div className="flex flex-wrap items-center gap-2 break-words text-sm text-[#6B7378]">
            <OverallRating rating={review.rating} />
            {review.publication_timestamp && <span>{new Date(review.publication_timestamp).toLocaleDateString()}</span>}
            {review.author_display_name && (review.reviewer_id && onOpenReviewer
              ? <button type="button" onClick={(event) => onOpenReviewer(review.reviewer_id!, review.id, event.currentTarget)} className="text-left underline hover:text-[#35647C]">By {review.author_display_name}</button>
              : <span>By {review.author_display_name}</span>)}
            {review.source_labels.map((label) => <span key={label}>Source: {label}</span>)}
          </div>
          <p className="mt-2 whitespace-pre-wrap break-words leading-6 text-[#24313A]">{review.text || review.original_text || 'No review text available.'}</p>
          <ReviewRichData details={review.details} translatedDetails={review.translated_details} images={review.images} />
          {review.canonical_source_url && <a className="mt-2 inline-block break-all text-sm text-[#35647C] underline" href={review.canonical_source_url} target="_blank" rel="noreferrer">Original review</a>}
        </article>
      ))}
    </div>
  )
}
