import { useState } from 'react'
import { MobileFilterSheet } from './MobileFilterSheet'
import { MobileRestaurantBar } from './MobileRestaurantBar'
import { ReviewFilters } from './ReviewFilters'
import { ReviewList } from './ReviewList'
import { ReviewTopicChips } from './ReviewTopicChips'
import type { ReviewFiltersProps, WorkspaceProps } from '../types/ui'

export function RestaurantReviewPane({
  selectedPlace,
  selectedSearchResult,
  setMobilePane,
  onMobileBack,
  reviewsQuery,
  visibleReviews,
  filterText,
  setFilterText,
  exactRating,
  setExactRating,
  reviewSort,
  setReviewSort,
  reviewerLabel,
  setReviewerLabel,
  reviewerLabelOptions,
  syncPending,
  refreshPending,
  reviewOperationNotice,
  onSync,
  onRefresh,
  filterPending,
  onFilter,
  onResetReviewControls,
  filterError,
  effectiveTotal,
  effectiveFilteredTotal
}: WorkspaceProps) {
  const [filtersOpen, setFiltersOpen] = useState(false)

  if (!selectedPlace) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center text-[#7B746C]">
        <div>
          <h2 className="text-2xl font-semibold text-[#4B5A63]">Select a restaurant</h2>
          <p className="mt-2 max-w-md">Choose a result on the left to open saved reviews and filtering controls.</p>
          <button onClick={() => setMobilePane('results')} className="mt-5 min-h-11 rounded-xl border border-[#CFC6BA] px-4 py-2 text-sm text-[#24313A] lg:hidden">
            Back to results
          </button>
        </div>
      </div>
    )
  }

  const hasReviews = Boolean(reviewsQuery.data?.total)
  const activeFilterCount = [exactRating, reviewerLabel, filterText.trim()].filter(Boolean).length
  const topics = reviewsQuery.data?.topics ?? []
  const filterProps: ReviewFiltersProps = {
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
    canFilter: hasReviews,
    effectiveTotal,
    effectiveFilteredTotal,
    onFilter,
    onResetReviewControls,
    filterError
  }

  const selectTopic = (keyword: string) => {
    setFilterText(keyword)
    onFilter(keyword)
  }

  return (
    <div className="min-w-0">
      <MobileRestaurantBar
        restaurantName={selectedPlace.display_name}
        activeFilterCount={activeFilterCount}
        onBack={onMobileBack}
        onOpenFilters={() => setFiltersOpen(true)}
      />

      <div className="border-b border-[#DED8CE] bg-[#FFFDFC] px-4 py-4 sm:px-6 lg:sticky lg:top-0 lg:z-10 lg:bg-[#FFFDFC]/95 lg:backdrop-blur">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold lg:block">{selectedPlace.display_name}</h1>
            <p className="break-words text-sm text-[#6B7378] lg:mt-1">{selectedPlace.formatted_address}</p>
            {(selectedSearchResult?.rating || selectedSearchResult?.distance_meters !== null && selectedSearchResult?.distance_meters !== undefined) && (
              <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-[#6B7378]">
                {selectedSearchResult?.rating && (
                  <span><span className="font-semibold text-[#E3A333]">{selectedSearchResult.rating.toFixed(1)}★</span>{selectedSearchResult.user_rating_count ? ` · ${selectedSearchResult.user_rating_count.toLocaleString()} reviews` : ''}</span>
                )}
                {selectedSearchResult?.distance_meters !== null && selectedSearchResult?.distance_meters !== undefined && (
                  <span className="text-[#35647C]">{(selectedSearchResult.distance_meters / 1609.344).toFixed(1)} mi away</span>
                )}
              </p>
            )}
            {selectedPlace.google_maps_url && (
              <a className="mt-2 inline-block break-all text-sm text-[#35647C] underline" href={selectedPlace.google_maps_url} target="_blank" rel="noreferrer">
                View on Google Maps
              </a>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button disabled={syncPending || refreshPending} onClick={onSync} className="min-h-11 rounded-xl bg-[#B7462D] px-4 py-2 font-semibold text-[#FFFDFC] hover:bg-[#9F3C27] disabled:opacity-50">
              {syncPending ? 'Fetching…' : reviewsQuery.data?.total ? 'Sync reviews' : 'Fetch reviews'}
            </button>
            <button disabled={syncPending || refreshPending || !(reviewsQuery.data?.total)} onClick={onRefresh} className="min-h-11 rounded-xl border border-[#CFC6BA] px-4 py-2 font-semibold text-[#24313A] hover:border-[#B7462D] disabled:opacity-50">
              {refreshPending ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
        </div>
        {reviewOperationNotice && (
          <div
            role="status"
            aria-live="polite"
            className={`mt-3 flex items-start gap-2 rounded-xl border px-3 py-2 text-sm ${
              reviewOperationNotice.kind === 'error'
                ? 'border-[#E4B7AA] bg-[#FFF5F2] text-[#8E321F]'
                : reviewOperationNotice.kind === 'success'
                  ? 'border-[#B8D4C4] bg-[#F3FAF6] text-[#285A42]'
                  : 'border-[#B8CDD8] bg-[#F3F8FA] text-[#35647C]'
            }`}
          >
            <span
              aria-hidden="true"
              className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                reviewOperationNotice.kind === 'pending' ? 'animate-pulse bg-[#35647C]' : reviewOperationNotice.kind === 'success' ? 'bg-[#3E7A5C]' : 'bg-[#B7462D]'
              }`}
            />
            <span>{reviewOperationNotice.text}</span>
          </div>
        )}
        {hasReviews && (
          <div className="hidden lg:block">
            <ReviewFilters {...filterProps} />
          </div>
        )}
      </div>

      <div className="mx-auto max-w-4xl space-y-5 px-4 py-5 sm:px-6">
        {hasReviews && <ReviewTopicChips topics={topics} disabled={filterPending} onSelect={selectTopic} />}
        <ReviewList
          reviews={visibleReviews}
          loading={reviewsQuery.isLoading}
          total={effectiveTotal}
          filteredTotal={effectiveFilteredTotal}
          exactRating={exactRating}
        />
      </div>

      {hasReviews && (
        <MobileFilterSheet
          {...filterProps}
          open={filtersOpen}
          onClose={() => setFiltersOpen(false)}
        />
      )}
    </div>
  )
}
