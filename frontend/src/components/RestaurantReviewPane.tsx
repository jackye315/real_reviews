import { useState } from 'react'
import { MobileFilterSheet } from './MobileFilterSheet'
import { MobileRestaurantBar } from './MobileRestaurantBar'
import { ReviewFilters } from './ReviewFilters'
import { ReviewList } from './ReviewList'
import { ReviewTopicChips } from './ReviewTopicChips'
import { ReviewerPane } from './ReviewerPane'
import { RestaurantInsights } from './RestaurantInsights'
import type { ReviewFiltersProps, WorkspaceProps } from '../types/ui'

export function RestaurantReviewPane({
  selectedPlace,
  selectedSearchResult,
  setMobilePane,
  onMobileBack,
  reviewsQuery,
  visibleReviews,
  reviewerRoute,
  reviewerContext,
  reviewerContextLoading,
  reviewerContextError,
  reviewerTimeWindow,
  onReviewerTimeWindowChange,
  onOpenReviewer,
  onCloseReviewer,
  onAnalyzeReviewer,
  onRefreshReviewer,
  onDeleteReviewer,
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
  checkNewPending,
  reviewOperationNotice,
  activeProviderOperation,
  onSync,
  onRefresh,
  onCheckNew,
  onCancelProviderOperation,
  savedHasMore,
  savedMorePending,
  onShowMoreSaved,
  loadMoreChoices,
  loadMorePending,
  loadMoreRecovery,
  onFetchOlder,
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
    relevanceAvailable: Boolean(reviewsQuery.data?.relevance_available),
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
        onOpenFilters={reviewerRoute ? undefined : () => setFiltersOpen(true)}
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
            {hasReviews && <p className="mt-2 text-xs text-[#6B7378]">{reviewsQuery.data?.relevance_available ? `Relevance ${reviewsQuery.data.relevance_status ?? 'saved'} · ${reviewsQuery.data.relevance_ranked_count ?? 0} ranked reviews${reviewsQuery.data.relevance_fetched_at ? ` · ${new Date(reviewsQuery.data.relevance_fetched_at).toLocaleDateString()}` : ''}` : 'Relevance not fetched'}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            {!hasReviews && (
              <button disabled={syncPending || refreshPending} onClick={onSync} className="min-h-11 rounded-xl bg-[#B7462D] px-4 py-2 font-semibold text-[#FFFDFC] hover:bg-[#9F3C27] disabled:opacity-50">
                {syncPending ? 'Fetching…' : 'Fetch reviews'}
              </button>
            )}
            <button disabled={syncPending || refreshPending || checkNewPending || !(reviewsQuery.data?.total)} onClick={onRefresh} className="min-h-11 rounded-xl border border-[#CFC6BA] px-4 py-2 font-semibold text-[#24313A] hover:border-[#B7462D] disabled:opacity-50">
              {refreshPending ? 'Refreshing relevance…' : 'Refresh relevance'}
            </button>
            {hasReviews && <button disabled={syncPending || refreshPending || checkNewPending} onClick={onCheckNew} className="min-h-11 rounded-xl border border-[#CFC6BA] px-4 py-2 font-semibold text-[#24313A] hover:border-[#B7462D] disabled:opacity-50">
              {checkNewPending ? 'Checking…' : 'Check for new reviews'}
            </button>}
            {activeProviderOperation && ['reserved', 'running'].includes(activeProviderOperation.status) && (
              <button onClick={onCancelProviderOperation} className="min-h-11 rounded-xl border border-[#B7462D] px-4 py-2 font-semibold text-[#B7462D] hover:bg-[#FFF5F2]">
                {activeProviderOperation.cancel_requested_at ? 'Cancellation requested…' : 'Cancel'}
              </button>
            )}
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
        {hasReviews && !reviewerRoute && (
          <div className="hidden lg:block">
            <ReviewFilters {...filterProps} />
          </div>
        )}
      </div>

      {reviewerRoute ? (
        <ReviewerPane
          context={reviewerContext}
          loading={reviewerContextLoading}
          error={reviewerContextError}
          onBack={onCloseReviewer}
          timeWindow={reviewerTimeWindow}
          onTimeWindowChange={onReviewerTimeWindowChange}
          onAnalyze={onAnalyzeReviewer}
          onRefresh={onRefreshReviewer}
          onDelete={onDeleteReviewer}
        />
      ) : <>
        <div className="mx-auto w-full max-w-6xl space-y-4 px-4 py-4 sm:px-6">
          <RestaurantInsights placeId={selectedPlace.google_place_id} initialDishSummary={selectedPlace.llm_dish_summary} visibleReviews={visibleReviews} />
          {hasReviews && <ReviewTopicChips topics={topics} disabled={filterPending} onSelect={selectTopic} />}
          <ReviewList reviews={visibleReviews} loading={reviewsQuery.isLoading} total={effectiveTotal} filteredTotal={effectiveFilteredTotal} exactRating={exactRating} onOpenReviewer={onOpenReviewer} />
          {savedHasMore && <button type="button" onClick={onShowMoreSaved} disabled={savedMorePending} className="min-h-11 rounded-xl border border-[#CFC6BA] px-4 py-2 text-sm font-semibold disabled:opacity-50">{savedMorePending ? 'Loading saved reviews…' : 'Show more saved reviews'}</button>}
          {hasReviews && loadMoreChoices.length > 0 && (
            <section aria-label="Fetch more relevant reviews" className="rounded-xl border border-[#DED8CE] bg-[#FFFDFC] p-4">
              <h2 className="font-semibold">Fetch more relevant reviews</h2>
              <p className="mt-1 text-sm text-[#6B7378]">Uses SerpApi qualityScore order. Records inspected are not guaranteed new reviews.</p>
              {loadMoreRecovery ? <button type="button" onClick={() => onFetchOlder(50, true)} disabled={loadMorePending} className="mt-3 min-h-11 rounded-xl bg-[#B7462D] px-3 py-2 text-sm font-semibold text-[#FFFDFC] disabled:opacity-50">Restart relevance from rank 1 (~{loadMoreRecovery.recovery_estimated_request_count ?? 0} requests)</button> : <div className="mt-3 flex flex-wrap gap-2">{loadMoreChoices.map((choice) => <button key={choice.provider_record_count} type="button" disabled={!choice.allowed || loadMorePending} onClick={() => onFetchOlder(choice.provider_record_count)} className="min-h-11 rounded-xl border border-[#CFC6BA] px-3 py-2 text-sm font-semibold disabled:opacity-50">{choice.provider_record_count} records (~{choice.estimated_request_count} request{choice.estimated_request_count === 1 ? '' : 's'})</button>)}</div>}
            </section>
          )}
        </div>
        {hasReviews && <MobileFilterSheet {...filterProps} open={filtersOpen} onClose={() => setFiltersOpen(false)} />}
      </>}
    </div>
  )
}
