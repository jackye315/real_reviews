import { Autocomplete } from './Autocomplete'
import { SearchForm } from './SearchForm'
import { SearchResultList } from './SearchResultList'
import type { WorkspaceProps } from '../types/ui'

export function SearchPane({
  searchQuery,
  setSearchQuery,
  onSubmit,
  isSearching,
  onAutocompleteSelected,
  searchResults,
  selectedPlace,
  nextSearchPageToken,
  onLoadNext,
  onSelectResult,
  message
}: WorkspaceProps) {
  return (
    <div className="p-4">
      <div className="sticky top-0 z-10 -mx-4 border-b border-[#DED8CE] bg-[#F7F4EE]/95 px-4 pb-4 backdrop-blur">
        <div className="space-y-3">
          <Autocomplete onSelected={onAutocompleteSelected} />
          <SearchForm searchQuery={searchQuery} setSearchQuery={setSearchQuery} onSubmit={onSubmit} isSearching={isSearching} compact />
          {message && <p className="text-xs text-[#6B7378]">{message}</p>}
        </div>
      </div>
      <SearchResultList
        results={searchResults}
        selectedPlaceId={selectedPlace?.google_place_id ?? null}
        onSelect={onSelectResult}
        nextPageToken={nextSearchPageToken}
        onLoadNext={onLoadNext}
        isLoadingNext={isSearching}
      />
    </div>
  )
}
