import type { RestaurantSearchResult } from '../types/api'

export function SearchResultList({
  results,
  selectedPlaceId,
  onSelect,
  nextPageToken,
  onLoadNext,
  isLoadingNext
}: {
  results: RestaurantSearchResult[]
  selectedPlaceId: string | null
  onSelect: (result: RestaurantSearchResult) => void
  nextPageToken: string | null
  onLoadNext: () => void
  isLoadingNext: boolean
}) {
  if (!results.length) return <p className="py-8 text-sm text-[#7B746C]">Search results will appear here.</p>
  return (
    <div className="-mx-4">
      {results.map((result) => {
        const selected = result.google_place_id === selectedPlaceId
        return (
          <button
            key={result.google_place_id}
            onClick={() => onSelect(result)}
            className={`grid w-full grid-cols-[4px_1fr] border-b border-[#DED8CE] text-left transition-colors hover:bg-[#FFFDFC] focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#B7462D] ${selected ? 'bg-[#B7462D]/10' : ''}`}
          >
            <span className={selected ? 'bg-[#B7462D]' : 'bg-transparent'} />
            <span className="px-4 py-3">
              <span className="block font-medium text-[#24313A]">{result.display_name}</span>
              <span className="mt-1 block text-sm text-[#6B7378]">{result.formatted_address}</span>
              <span className="mt-1 block text-xs text-[#7B746C]">
                {result.rating ? `${result.rating.toFixed(1)}★` : 'No rating'}
                {result.user_rating_count ? ` · ${result.user_rating_count.toLocaleString()} reviews` : ''}
                {result.distance_meters !== null && result.distance_meters !== undefined
                  ? ` · ${(result.distance_meters / 1609.344).toFixed(1)} mi away`
                  : ''}
              </span>
            </span>
          </button>
        )
      })}
      {nextPageToken && (
        <button onClick={onLoadNext} disabled={isLoadingNext} className="w-full border-b border-[#DED8CE] px-4 py-3 text-sm text-[#35647C] hover:bg-[#FFFDFC] disabled:opacity-50">
          {isLoadingNext ? 'Loading…' : 'Load next search page'}
        </button>
      )}
    </div>
  )
}
