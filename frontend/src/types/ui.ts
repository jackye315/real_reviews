import type { Dispatch, FormEvent, RefObject, SetStateAction } from 'react'
import type { ReviewerContext } from './api'
import type { PlaceResponse, ProviderOperation, ProviderUsage, RestaurantSearchResult, Review, ReviewListResponse, ReviewerLabelOption, ReviewSort } from './api'
import type { Autocomplete } from '../components/Autocomplete'

export type WorkspaceMode = 'landing' | 'workspace'
export type MobilePane = 'results' | 'reviews'
export type SearchSelection = Parameters<typeof Autocomplete>[0]['onSelected']
export type ReviewOperationNotice = {
  kind: 'pending' | 'success' | 'error'
  text: string
}

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
  onMobileBack: () => void
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
  reviewsQuery: { data?: ReviewListResponse; isLoading: boolean }
  visibleReviews: Review[]
  reviewerRoute: { reviewerId: string; reviewId: string } | null
  reviewerContext?: ReviewerContext
  reviewerContextLoading: boolean
  reviewerContextError: string | null
  reviewerTimeWindow: 'six_months' | 'one_year' | 'two_years' | 'all_observed'
  onReviewerTimeWindowChange: (value: 'six_months' | 'one_year' | 'two_years' | 'all_observed') => void
  onOpenReviewer?: (reviewerId: string, reviewId: string, source: HTMLButtonElement) => void
  onCloseReviewer: () => void
  onAnalyzeReviewer: () => void
  onRefreshReviewer: () => void
  onDeleteReviewer: () => void
  reviewPaneRef: RefObject<HTMLElement | null>
  filterText: string
  setFilterText: (value: string) => void
  exactRating: string
  setExactRating: (value: string) => void
  reviewSort: ReviewSort
  setReviewSort: (value: ReviewSort) => void
  reviewerLabel: string
  setReviewerLabel: (value: string) => void
  reviewerLabelOptions: ReviewerLabelOption[]
  relevanceAvailable: boolean
  syncPending: boolean
  refreshPending: boolean
  checkNewPending: boolean
  reviewOperationNotice: ReviewOperationNotice | null
  activeProviderOperation: ProviderOperation | null
  onSync: () => void
  onRefresh: () => void
  onCheckNew: () => void
  onCancelProviderOperation: () => void
  savedHasMore: boolean
  savedMorePending: boolean
  onShowMoreSaved: () => void
  loadMoreChoices: { provider_record_count: 20 | 50 | 100; estimated_request_count: number; allowed: boolean }[]
  loadMorePending: boolean
  loadMoreRecovery: ProviderOperation | null
  onFetchOlder: (target: 20 | 50 | 100, restart?: boolean) => void
  filterPending: boolean
  onFilter: (filterTextOverride?: string) => void
  onResetReviewControls: () => void
  filterError: string | null
  effectiveTotal: number
  effectiveFilteredTotal: number
}

export type ReviewFiltersProps = Pick<
  WorkspaceProps,
  | 'filterText'
  | 'setFilterText'
  | 'exactRating'
  | 'setExactRating'
  | 'reviewSort'
  | 'setReviewSort'
  | 'reviewerLabel'
  | 'setReviewerLabel'
  | 'reviewerLabelOptions'
  | 'relevanceAvailable'
  | 'filterPending'
  | 'onFilter'
  | 'onResetReviewControls'
  | 'filterError'
  | 'effectiveTotal'
  | 'effectiveFilteredTotal'
> & {
  canFilter: boolean
  compact?: boolean
}

export type DeveloperDrawerProps = {
  open: boolean
  usage: ProviderUsage[]
  operations: ProviderOperation[]
  loading: boolean
  onRefresh: () => void
  onClose: () => void
}
