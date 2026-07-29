import type { Review } from '../types/api'

export function ReviewList({ reviews, loading }: { reviews: Review[]; loading: boolean }) {
  if (loading) return <p className="text-[#6B7378]">Loading stored reviews…</p>
  if (!reviews.length) return <p className="text-[#6B7378]">No stored reviews yet. Fetch reviews to load topics and review filtering controls.</p>
  return (
    <div className="grid gap-4">
      {reviews.map((review) => (
        <article key={review.id} className="rounded-2xl border border-[#DED8CE] bg-[#FFFDFC] p-4">
          <div className="flex flex-wrap items-center gap-3 text-sm text-[#6B7378]">
            <span className="font-semibold text-[#E3A333]">{review.rating ? `${review.rating}★` : 'No rating'}</span>
            {review.publication_timestamp && <span>{new Date(review.publication_timestamp).toLocaleDateString()}</span>}
            {review.author_display_name && <span>By {review.author_display_name}</span>}
            {review.source_labels.map((label) => <span key={label}>Source: {label}</span>)}
          </div>
          <p className="mt-3 whitespace-pre-wrap leading-7 text-[#24313A]">{review.text || review.original_text || 'No review text available.'}</p>
          {review.canonical_source_url && <a className="mt-3 inline-block text-sm text-[#35647C] underline" href={review.canonical_source_url} target="_blank" rel="noreferrer">Original review</a>}
        </article>
      ))}
    </div>
  )
}
