import type { ReviewFiltersProps } from '../types/ui'

export function ReviewFilters({
  filterText,
  setFilterText,
  exactRating,
  setExactRating,
  reviewSort,
  setReviewSort,
  reviewerLabel,
  setReviewerLabel,
  reviewerLabelOptions,
  filterPending,
  canFilter,
  effectiveTotal,
  effectiveFilteredTotal,
  onFilter,
  onResetReviewControls,
  filterError,
  compact = false
}: ReviewFiltersProps) {
  return (
    <div className={compact ? 'space-y-3' : 'mt-4 space-y-3'}>
      <div className={compact ? 'grid gap-3' : 'grid gap-2 md:grid-cols-2 xl:grid-cols-[auto_auto_auto_1fr_auto_auto]'}>
        <select
          value={exactRating}
          onChange={(event) => setExactRating(event.target.value)}
          disabled={filterPending}
          className="min-h-11 rounded-xl border border-[#CFC6BA] bg-[#FFFDFC] px-3 py-2 text-[#24313A] outline-none ring-[#B7462D] focus:ring-2 disabled:cursor-wait disabled:opacity-60"
          aria-label="Exact rating"
        >
          <option value="">Any rating</option>
          <option value="5">5 stars</option>
          <option value="4">4 stars</option>
          <option value="3">3 stars</option>
          <option value="2">2 stars</option>
          <option value="1">1 star</option>
        </select>
        <select
          value={reviewerLabel}
          onChange={(event) => setReviewerLabel(event.target.value)}
          disabled={filterPending}
          className="min-h-11 rounded-xl border border-[#CFC6BA] bg-[#FFFDFC] px-3 py-2 text-[#24313A] outline-none ring-[#B7462D] focus:ring-2 disabled:cursor-wait disabled:opacity-60"
          aria-label="Reviewer label"
        >
          <option value="">Any reviewer label</option>
          {reviewerLabelOptions.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
        <select
          value={reviewSort}
          onChange={(event) => setReviewSort(event.target.value as typeof reviewSort)}
          disabled={filterPending}
          className="min-h-11 rounded-xl border border-[#CFC6BA] bg-[#FFFDFC] px-3 py-2 text-[#24313A] outline-none ring-[#B7462D] focus:ring-2 disabled:cursor-wait disabled:opacity-60"
          aria-label="Review sort"
        >
          <option value="recent">Most recent</option>
          <option value="oldest">Oldest</option>
          <option value="rating_high">Highest rated</option>
          <option value="rating_low">Lowest rated</option>
        </select>
        <input
          value={filterText}
          onChange={(event) => setFilterText(event.target.value)}
          disabled={filterPending}
          className="min-h-11 min-w-0 rounded-xl border border-[#CFC6BA] bg-[#FFFDFC] px-3 py-2 text-[#24313A] outline-none ring-[#B7462D] focus:ring-2 disabled:cursor-wait disabled:opacity-60"
          placeholder="mentions spicy noodles, slow service, good mocktails…"
        />
        <button disabled={!filterText || filterPending || !canFilter} onClick={() => onFilter()} className="min-h-11 rounded-xl bg-[#B7462D] px-4 py-2 font-semibold text-[#FFFDFC] hover:bg-[#9F3C27] disabled:opacity-50">
          {filterPending ? 'Thinking…' : 'Filter'}
        </button>
        <button onClick={onResetReviewControls} className="min-h-11 rounded-xl border border-[#CFC6BA] px-4 py-2 text-[#24313A]">
          Reset
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-sm text-[#6B7378]">
        <span>{effectiveFilteredTotal.toLocaleString()} of {effectiveTotal.toLocaleString()} reviews</span>
        {filterPending && (
          <span className="inline-flex items-center gap-2 font-medium text-[#35647C]" role="status" aria-live="polite">
            <span className="h-2 w-2 animate-pulse rounded-full bg-[#35647C]" />
            Filtering with local LLM…
          </span>
        )}
        {filterError && (
          <span className="text-[#B7462D]">
            {filterError}{' '}
            <button type="button" onClick={() => onFilter()} disabled={filterPending} className="text-[#35647C] underline disabled:opacity-50">
              Retry
            </button>
          </span>
        )}
      </div>
    </div>
  )
}
