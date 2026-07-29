import { ReviewFilters } from './ReviewFilters'
import { ReviewList } from './ReviewList'
import type { WorkspaceProps } from '../types/ui'

export function RestaurantReviewPane({
  selectedPlace,
  selectedSearchResult,
  setMobilePane,
  reviewsQuery,
  visibleReviews,
  filterText,
  setFilterText,
  minRating,
  setMinRating,
  selectedReviewIds,
  setSelectedReviewIds,
  syncPending,
  refreshPending,
  onSync,
  onRefresh,
  filterPending,
  onFilter
}: WorkspaceProps) {
  if (!selectedPlace) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center text-[#7B746C]">
        <div>
          <h2 className="text-2xl font-semibold text-[#4B5A63]">Select a restaurant</h2>
          <p className="mt-2 max-w-md">Choose a result on the left to open saved reviews and filtering controls.</p>
          <button onClick={() => setMobilePane('results')} className="mt-5 rounded-xl border border-[#CFC6BA] px-4 py-2 text-sm text-[#24313A] lg:hidden">
            Back to results
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="sticky top-0 z-10 border-b border-[#DED8CE] bg-[#FFFDFC]/95 px-4 py-4 backdrop-blur sm:px-6">
        <button onClick={() => setMobilePane('results')} className="mb-3 rounded-xl border border-[#CFC6BA] px-3 py-1.5 text-sm text-[#24313A] lg:hidden">
          Back to results
        </button>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold">{selectedPlace.display_name}</h1>
            <p className="mt-1 text-sm text-[#6B7378]">{selectedPlace.formatted_address}</p>
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
              <a className="mt-2 inline-block text-sm text-[#35647C] underline" href={selectedPlace.google_maps_url} target="_blank" rel="noreferrer">
                View on Google Maps
              </a>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button disabled={syncPending || refreshPending} onClick={onSync} className="rounded-xl bg-[#B7462D] px-4 py-2 font-semibold text-[#FFFDFC] hover:bg-[#9F3C27] disabled:opacity-50">
              {syncPending ? 'Fetching…' : reviewsQuery.data?.reviews.length ? 'Sync reviews' : 'Fetch reviews'}
            </button>
            <button disabled={syncPending || refreshPending || !(reviewsQuery.data?.reviews.length)} onClick={onRefresh} className="rounded-xl border border-[#CFC6BA] px-4 py-2 font-semibold text-[#24313A] hover:border-[#B7462D] disabled:opacity-50">
              {refreshPending ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>
        </div>
        {Boolean(reviewsQuery.data?.reviews.length) && (
          <ReviewFilters
            filterText={filterText}
            setFilterText={setFilterText}
            minRating={minRating}
            setMinRating={setMinRating}
            selectedReviewIds={selectedReviewIds}
            setSelectedReviewIds={setSelectedReviewIds}
            filterPending={filterPending}
            canFilter={Boolean(reviewsQuery.data?.reviews.length)}
            topics={reviewsQuery.data?.topics ?? []}
            onFilter={onFilter}
          />
        )}
      </div>
      <div className="mx-auto max-w-4xl px-4 py-5 sm:px-6">
        <ReviewList reviews={visibleReviews} loading={reviewsQuery.isLoading} />
      </div>
    </div>
  )
}
