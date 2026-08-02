import { useEffect, useState } from 'react'
import type { ReviewerComparison, ReviewerContext, ReviewerRelevantReview } from '../types/api'

type TimeWindow = 'six_months' | 'one_year' | 'two_years' | 'all_observed'

const INITIAL_VISIBLE_REVIEWS = 5
const REVIEW_PREVIEW_LENGTH = 320

const WINDOW_LABELS: Record<TimeWindow, string> = {
  six_months: 'Last 6 months',
  one_year: 'Last year',
  two_years: 'Last 2 years',
  all_observed: 'All observed'
}

function humanize(value?: string | null) {
  if (!value) return 'matching category'
  const text = value.replace(/_/g, ' ').toLowerCase()
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}`
}

function pluralize(value: string) {
  if (value.endsWith('y')) return `${value.slice(0, -1)}ies`
  if (value.endsWith('s')) return value
  return `${value}s`
}

function Rating({ rating }: { rating: number }) {
  return <span aria-label={`${rating} out of 5 stars`} className="font-medium text-[#24313A]">
    {rating} <span aria-hidden="true" className="text-[#D9901A]">{'★'.repeat(rating)}</span>
  </span>
}

function RelevantReviewRow({ review }: { review: ReviewerRelevantReview }) {
  const [expanded, setExpanded] = useState(false)
  const body = review.text || review.original_text || ''
  const canExpand = body.length > REVIEW_PREVIEW_LENGTH
  const displayedBody = canExpand && !expanded
    ? `${body.slice(0, REVIEW_PREVIEW_LENGTH).trimEnd()}…`
    : body

  useEffect(() => setExpanded(false), [review.id, body])

  return <li className="border-t border-[#E5DED4] py-3 first:border-t-0">
    <article aria-labelledby={`review-place-${review.id}`}>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div>
          <h4 id={`review-place-${review.id}`} className="font-semibold text-[#24313A]">{review.place_name}</h4>
          <p className="mt-0.5 text-sm text-[#6B7378]">
            <Rating rating={review.rating} />
            {review.provider_date_text ? ` · ${review.provider_date_text}` : ''}
            {review.publication_date_is_approximate ? ' (approximate)' : ''}
          </p>
        </div>
        {review.source_url && <a href={review.source_url} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-[#35647C] underline underline-offset-2">Open on Google</a>}
      </div>
      <p className="mt-1.5 whitespace-pre-wrap text-sm leading-6 text-[#34434D]">
        {displayedBody || 'No written review.'}
      </p>
      {canExpand && <button type="button" onClick={() => setExpanded((value) => !value)} className="mt-2 text-sm font-semibold text-[#35647C] underline underline-offset-2" aria-expanded={expanded}>
        {expanded ? 'Show less' : 'Show full review'}
      </button>}
    </article>
  </li>
}

function RelevantReviewList({ reviews, total, resetKey }: {
  reviews: ReviewerRelevantReview[]
  total: number
  resetKey: string
}) {
  const [showAll, setShowAll] = useState(false)

  useEffect(() => setShowAll(false), [resetKey])

  const visibleReviews = showAll ? reviews : reviews.slice(0, INITIAL_VISIBLE_REVIEWS)
  const hasMore = reviews.length > INITIAL_VISIBLE_REVIEWS

  return <div className="mt-4 border-t border-[#DED8CE] pt-3">
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h3 className="font-semibold text-[#24313A]">Reviews used in this comparison</h3>
      <p className="text-xs text-[#6B7378]">
        Showing {visibleReviews.length} of {total}
      </p>
    </div>
    <ul className="mt-2" aria-label="Reviews used in this comparison">
      {visibleReviews.map((review) => <RelevantReviewRow key={review.id} review={review} />)}
    </ul>
    {hasMore && <button type="button" onClick={() => setShowAll((value) => !value)} className="mt-2 min-h-11 rounded-xl border border-[#CFC6BA] bg-[#FFFDFC] px-4 py-2 text-sm font-semibold text-[#35647C]" aria-expanded={showAll}>
      {showAll ? 'Show fewer reviews' : `Show all ${reviews.length} reviews`}
    </button>}
  </div>
}

function ComparisonSummary({ comparison, broader }: {
  comparison: ReviewerComparison
  broader?: boolean
}) {
  const category = humanize(broader ? comparison.comparison_family : comparison.normalized_venue_type)
  const label = broader ? 'Broader restaurants' : `Other ${pluralize(category.toLowerCase())}`

  return <section className="min-w-0 py-2 md:px-4 md:first:pl-0 md:last:pr-0" aria-label={`${label} rating summary`}>
    <h3 className="text-sm font-semibold text-[#24313A]">{label}</h3>
    <p className="mt-0.5 text-xs text-[#6B7378]">{comparison.sample_size} observed · {WINDOW_LABELS[comparison.time_window]}</p>

    {!comparison.sample_size ? <p className="mt-2 text-sm text-[#6B7378]">No other matching reviews</p> : comparison.sample_size <= 2 ? <p className="mt-2 text-sm"><span className="text-[#6B7378]">Ratings</span> <strong>{comparison.individual_ratings.join(', ')} stars</strong></p> : <div className="mt-2 grid gap-3 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] xl:items-end">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <div><dt className="text-xs text-[#6B7378]">Average</dt><dd className="font-semibold">{comparison.average_rating?.toFixed(1) ?? '—'} stars</dd></div>
        <div><dt className="text-xs text-[#6B7378]">Median</dt><dd className="font-semibold">{comparison.median_rating?.toFixed(1) ?? '—'} stars</dd></div>
        <div className="col-span-2"><dt className="text-xs text-[#6B7378]">Standard deviation</dt><dd className="font-semibold">{comparison.standard_deviation?.toFixed(2) ?? '—'}{comparison.sample_size < 5 ? ' · Small sample' : ''}</dd></div>
      </dl>
      <div aria-label="Rating distribution">
        <p className="text-xs text-[#6B7378]">Distribution</p>
        <div className="mt-1 grid grid-cols-5 gap-1 text-center text-xs">
          {[1, 2, 3, 4, 5].map((rating) => <span key={rating} className="rounded-md bg-[#F1ECE4] px-1 py-1.5"><span className="block text-[#6B7378]">{rating}★</span><strong className="block text-[#24313A]">{comparison.rating_distribution[String(rating)] ?? 0}</strong></span>)}
        </div>
      </div>
    </div>}
  </section>
}

function ComparisonSurface({ comparison, broader }: {
  comparison: ReviewerComparison
  broader?: boolean
}) {
  const category = humanize(broader ? comparison.comparison_family : comparison.normalized_venue_type)
  const categoryLower = category.toLowerCase()
  const categoryPlural = pluralize(categoryLower)
  const heading = broader ? 'Broader restaurant comparison' : `Other ${categoryPlural}`
  const sampleLabel = broader ? `Broader ${categoryLower} comparison` : `Exact ${categoryLower} comparison`
  const sampleNoun = broader ? 'restaurants' : categoryPlural
  const reviews = comparison.relevant_reviews ?? []

  return <section className="rounded-2xl border border-[#DED8CE] bg-[#FFFDFC] p-4" aria-label={sampleLabel}>
    <header>
      <h2 className="text-lg font-semibold text-[#24313A]">{heading}</h2>
      <p className="mt-1 text-sm text-[#6B7378]">{sampleLabel} · {WINDOW_LABELS[comparison.time_window]}</p>
    </header>

    {!comparison.sample_size ? <p className="mt-4 text-sm">No other {categoryLower} reviews observed.</p> : <>
      <p className="mt-4 font-medium">{comparison.sample_size} other {sampleNoun} observed</p>
      {comparison.sample_size <= 2 && <p className="mt-2 text-sm">Observed ratings: {comparison.individual_ratings.join(', ')} stars</p>}
      {reviews.length > 0 && <RelevantReviewList
        reviews={reviews}
        total={comparison.sample_size}
        resetKey={`${comparison.time_window}:${comparison.match_level}:${reviews.map((review) => review.id).join(',')}`}
      />}
    </>}
    {comparison.contains_approximate_dates && <p className="mt-4 text-xs text-[#6B7378]">Some dates are approximate provider-displayed dates.</p>}
  </section>
}

export function ReviewerPane({ context, loading, error, onBack, timeWindow, onTimeWindowChange, onAnalyze, onRefresh, onDelete }: {
  context?: ReviewerContext
  loading: boolean
  error: string | null
  onBack: () => void
  timeWindow: TimeWindow
  onTimeWindowChange: (value: TimeWindow) => void
  onAnalyze: () => void
  onRefresh: () => void
  onDelete: () => void
}) {
  if (loading) return <section className="p-6 text-[#6B7378]"><h2 id="reviewer-heading" tabIndex={-1} className="text-lg font-semibold text-[#24313A]">Reviewer context</h2><p className="mt-2">Loading reviewer profile…</p></section>
  if (error || !context) return <section className="p-6"><button onClick={onBack} className="text-[#35647C] underline">← Back to reviews</button><h2 id="reviewer-heading" tabIndex={-1} className="mt-4 text-lg font-semibold">Reviewer context</h2><p className="mt-2 text-[#8E321F]">{error ?? 'Reviewer profile is unavailable.'}</p></section>

  const { reviewer, current, comparison, broader_comparison: broaderComparison } = context
  const hasContext = reviewer.context_generation > 0

  return <section className="mx-auto max-w-5xl p-4 sm:p-5">
    <button onClick={onBack} className="min-h-11 text-sm font-semibold text-[#35647C] underline">← Back to reviews</button>

    <div className="mt-3 border-b border-[#DED8CE] pb-4">
      <div className="space-y-3">
        <div className="flex gap-4">
          {reviewer.avatar_url && <img src={reviewer.avatar_url} alt="" className="h-12 w-12 rounded-full object-cover" referrerPolicy="no-referrer" />}
          <div><h1 id="reviewer-heading" tabIndex={-1} className="text-xl font-semibold">{reviewer.display_name ?? 'Public reviewer'}</h1><p className="text-sm text-[#6B7378]">{reviewer.local_guide ? 'Local Guide · ' : ''}{reviewer.provider_review_count?.toLocaleString() ?? 'Not available'} public Google reviews</p><p className="text-sm text-[#6B7378]">{reviewer.provider_photo_count?.toLocaleString() ?? 'Not available'} photos</p>{reviewer.profile_url && <a className="text-sm text-[#35647C] underline" href={reviewer.profile_url} target="_blank" rel="noopener noreferrer">View Google Maps profile</a>}</div>
        </div>
        {comparison && <div className="min-w-0 border-t border-[#E5DED4] pt-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="font-semibold text-[#24313A]">Rating overview</h2><p className="text-xs text-[#6B7378]">Calculated from saved reviewer history</p></div>
            <label className="text-sm font-medium">Window <select value={timeWindow} onChange={(event) => onTimeWindowChange(event.target.value as TimeWindow)} className="ml-2 min-h-11 rounded-lg border border-[#CFC6BA] bg-[#FFFDFC] px-3 py-2"><option value="six_months">Last 6 months</option><option value="one_year">Last year</option><option value="two_years">Last 2 years</option><option value="all_observed">All observed</option></select></label>
          </div>
          <div className={`mt-1 grid divide-y divide-[#DED8CE] ${broaderComparison ? comparison.sample_size === 0 ? 'md:grid-cols-[minmax(220px,0.65fr)_minmax(0,1.35fr)] md:divide-x md:divide-y-0' : 'md:grid-cols-2 md:divide-x md:divide-y-0' : ''}`}>
            <ComparisonSummary comparison={comparison} />
            {broaderComparison && <ComparisonSummary comparison={broaderComparison} broader />}
          </div>
        </div>}
      </div>
    </div>

    <div className="mt-4 space-y-3">
      <section className="rounded-2xl border border-[#DED8CE] bg-[#FFFDFC] p-4" aria-labelledby="original-review-heading">
        <p className="text-xs font-semibold uppercase tracking-wide text-[#6B7378]">Original restaurant review</p>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-2">
          <p id="original-review-heading" className="text-lg font-semibold text-[#24313A]">{current.restaurant_name}</p>
          {current.review.rating ? <Rating rating={current.review.rating} /> : <span className="text-sm text-[#6B7378]">No rating</span>}
        </div>
        <p className="mt-2 whitespace-pre-wrap leading-6">{current.review.text || current.review.original_text || 'No review text available.'}</p>
        {current.review.canonical_source_url && <a href={current.review.canonical_source_url} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-sm font-medium text-[#35647C] underline underline-offset-2">Open original on Google</a>}
      </section>

      {comparison && <>
        <ComparisonSurface comparison={comparison} />
        {broaderComparison && <ComparisonSurface comparison={broaderComparison} broader />}
      </>}
    </div>

    <div className="mt-5 flex flex-wrap gap-2">{!hasContext ? <button onClick={onAnalyze} className="min-h-11 rounded-xl bg-[#B7462D] px-4 py-2 font-semibold text-[#FFFDFC]">Analyze review history · may use 1 search</button> : <button onClick={onRefresh} className="min-h-11 rounded-xl border border-[#CFC6BA] px-4 py-2 font-semibold">Refresh history · may use 1 search</button>}{hasContext && <button onClick={onDelete} className="min-h-11 rounded-xl border border-[#B7462D] px-4 py-2 text-[#B7462D]">Delete saved context</button>}</div>
    {hasContext && <p className="mt-3 text-xs text-[#6B7378]">History fetched {reviewer.context_fetched_at ? new Date(reviewer.context_fetched_at).toLocaleDateString() : 'recently'} · {reviewer.provider_results_returned ?? 0} returned · {reviewer.accepted_food_and_drink_count ?? 0} supported food-and-drink reviews retained.</p>}
  </section>
}
