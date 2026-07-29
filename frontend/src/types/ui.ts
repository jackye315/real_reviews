import type { UseQueryResult } from '@tanstack/react-query'
import type { Dispatch, FormEvent, RefObject, SetStateAction } from 'react'
import type { PlaceResponse, ProviderUsage, RestaurantSearchResult, Review, ReviewListResponse, ReviewTopic } from './api'
import type { Autocomplete } from '../components/Autocomplete'

export type WorkspaceMode = 'landing' | 'workspace'
export type MobilePane = 'results' | 'reviews'
export type SearchSelection = Parameters<typeof Autocomplete>[0]['onSelected']

export type SearchFormProps = {
  searchQuery: string
  setSearchQuery: (value: string) => void
  onSubmit: (event?: FormEvent<HTMLFormElement>) => void
  isSearching: boolean
  compact?: boolean
}

export type AppChromeProps = {
  mode: WorkspaceMode
  developerButtonRef: RefObject<HTMLButtonElement | null>
  onDeveloperOpen: () => void
  onNewSearch: () => void
}

export type SearchLandingProps = {
  searchQuery: string
  setSearchQuery: (value: string) => void
  onSubmit: (event?: FormEvent<HTMLFormElement>) => void
  onAutocompleteSelected: SearchSelection
  isSearching: boolean
  message: string | null
}

export type WorkspaceProps = {
  mobilePane: MobilePane
  setMobilePane: Dispatch<SetStateAction<MobilePane>> | ((pane: MobilePane) => void)
  searchQuery: string
  setSearchQuery: (value: string) => void
  onSubmit: (event?: FormEvent<HTMLFormElement>) => void
  isSearching: boolean
  onAutocompleteSelected: SearchSelection
  searchResults: RestaurantSearchResult[]
  selectedPlace: PlaceResponse | null
  selectedSearchResult: RestaurantSearchResult | null
  nextSearchPageToken: string | null
  onLoadNext: () => void
  onSelectResult: (result: RestaurantSearchResult) => void
  message: string | null
  reviewsQuery: UseQueryResult<ReviewListResponse>
  visibleReviews: Review[]
  filterText: string
  setFilterText: (value: string) => void
  minRating: string
  setMinRating: (value: string) => void
  selectedReviewIds: string[] | null
  setSelectedReviewIds: (ids: string[] | null) => void
  syncPending: boolean
  refreshPending: boolean
  onSync: () => void
  onRefresh: () => void
  filterPending: boolean
  onFilter: (filterTextOverride?: string) => void
}

export type ReviewFiltersProps = Pick<
  WorkspaceProps,
  | 'filterText'
  | 'setFilterText'
  | 'minRating'
  | 'setMinRating'
  | 'selectedReviewIds'
  | 'setSelectedReviewIds'
  | 'filterPending'
  | 'onFilter'
> & {
  canFilter: boolean
  topics: ReviewTopic[]
}

export type DeveloperDrawerProps = {
  open: boolean
  usage: ProviderUsage[]
  loading: boolean
  onRefresh: () => void
  onClose: () => void
}
