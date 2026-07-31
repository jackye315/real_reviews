import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { AppChrome } from './components/AppChrome'
import { DeveloperDrawer } from './components/DeveloperDrawer'
import { SearchLanding } from './components/SearchLanding'
import { Workspace } from './components/Workspace'
import {
  filterReviews,
  getProviderUsage,
  getReviewFilterOptions,
  getReviews,
  persistSearchResult,
  persistSelection,
  refreshReviews,
  searchRestaurants,
  syncReviews
} from './lib/api'
import { useUserLocation } from './hooks/useUserLocation'
import type { PlaceResponse, RestaurantSearchResult, Review, ReviewFilterResponse, ReviewSort, ReviewTopic } from './types/api'
import type { MobilePane, ReviewOperationNotice, WorkspaceMode } from './types/ui'

function App() {
  const queryClient = useQueryClient()
  const userLocation = useUserLocation()
  const developerButtonRef = useRef<HTMLButtonElement | null>(null)
  const [mode, setMode] = useState<WorkspaceMode>('landing')
  const [mobilePane, setMobilePane] = useState<MobilePane>('results')
  const [developerOpen, setDeveloperOpen] = useState(false)
  const [selectedPlace, setSelectedPlace] = useState<PlaceResponse | null>(null)
  const [selectedSearchResult, setSelectedSearchResult] = useState<RestaurantSearchResult | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<RestaurantSearchResult[]>([])
  const [nextSearchPageToken, setNextSearchPageToken] = useState<string | null>(null)
  const [filterText, setFilterText] = useState('')
  const [exactRating, setExactRating] = useState('')
  const [reviewSort, setReviewSortState] = useState<ReviewSort>('recent')
  const [reviewerLabel, setReviewerLabelState] = useState('')
  const [semanticResponse, setSemanticResponse] = useState<ReviewFilterResponse | null>(null)
  const [filterError, setFilterError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [reviewOperationNotice, setReviewOperationNotice] = useState<ReviewOperationNotice | null>(null)

  useEffect(() => {
    window.history.replaceState({ rrView: 'landing' }, '', window.location.href)
    const onPopState = (event: PopStateEvent) => {
      const view = event.state?.rrView
      if (view === 'reviews') {
        setMode('workspace')
        setMobilePane('reviews')
      } else if (view === 'results') {
        setMode('workspace')
        setMobilePane('results')
      } else {
        setMode('landing')
        setMobilePane('results')
      }
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const pushHistoryView = useCallback((rrView: 'landing' | 'results' | 'reviews') => {
    if (window.history.state?.rrView !== rrView) {
      window.history.pushState({ rrView }, '', window.location.href)
    }
  }, [])

  const reviewsQuery = useQuery({
    queryKey: ['reviews', selectedPlace?.google_place_id, exactRating, reviewSort],
    queryFn: () => getReviews(selectedPlace!.google_place_id, exactRating ? Number(exactRating) : null, reviewSort),
    enabled: Boolean(selectedPlace),
    placeholderData: keepPreviousData
  })

  const filterOptionsQuery = useQuery({
    queryKey: ['reviewFilterOptions'],
    queryFn: getReviewFilterOptions,
    enabled: Boolean(selectedPlace && reviewsQuery.data?.total)
  })

  const usageQuery = useQuery({
    queryKey: ['providerUsage'],
    queryFn: getProviderUsage,
    enabled: developerOpen
  })

  const openWorkspaceWithPlace = useCallback((place: PlaceResponse, sourceResult: RestaurantSearchResult | null = null) => {
    setSelectedPlace(place)
    setSelectedSearchResult(sourceResult)
    setMode('workspace')
    setMobilePane('reviews')
    setFilterText('')
    setExactRating('')
    setReviewSortState('recent')
    setReviewerLabelState('')
    setSemanticResponse(null)
    setFilterError(null)
    setReviewOperationNotice(null)
    pushHistoryView('reviews')
    queryClient.invalidateQueries({ queryKey: ['reviews', place.google_place_id] })
  }, [pushHistoryView, queryClient])

  const autocompleteMetadataMutation = useMutation({
    mutationFn: (place: PlaceResponse) =>
      searchRestaurants(`${place.display_name} ${place.formatted_address ?? ''}`.trim(), null, userLocation),
    onSuccess: (page, place) => {
      const exactMatch = page.results.find((result) => result.google_place_id === place.google_place_id)
      if (exactMatch) setSelectedSearchResult(exactMatch)
    }
  })

  const autocompleteSelection = useMutation({
    mutationFn: persistSelection,
    onMutate: () => setMessage('Saving selected place…'),
    onSuccess: (place) => {
      openWorkspaceWithPlace(place)
      autocompleteMetadataMutation.mutate(place)
      setMessage(`Selected ${place.display_name}`)
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : 'Selection failed')
  })

  const searchMutation = useMutation({
    mutationFn: ({ query, pageToken }: { query: string; pageToken?: string | null }) =>
      searchRestaurants(query, pageToken, userLocation),
    onSuccess: (page, variables) => {
      setSearchResults((current) => (variables.pageToken ? [...current, ...page.results] : page.results))
      setNextSearchPageToken(page.next_page_token ?? null)
      setMode('workspace')
      setMobilePane('results')
      if (!variables.pageToken) pushHistoryView('results')
      if (!variables.pageToken) {
        setSelectedPlace(null)
        setSelectedSearchResult(null)
        setFilterText('')
        setExactRating('')
        setReviewSortState('recent')
        setReviewerLabelState('')
        setSemanticResponse(null)
        setFilterError(null)
      }
      setMessage(
        userLocation
          ? 'Showing 10 results per page, sorted by distance within each Google result page.'
          : 'Showing 10 results per page in Google search order. Allow location access to sort by distance.'
      )
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : 'Search failed')
  })

  const selectSearchResult = useMutation({
    mutationFn: persistSearchResult,
    onSuccess: (place, result) => {
      openWorkspaceWithPlace(place, result)
      setMessage(`Selected ${place.display_name}`)
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : 'Selection failed')
  })

  const applyReviewSyncResponse = (operation: 'Sync' | 'Refresh', response: {
    reviews: Review[]
    topics?: ReviewTopic[]
    topics_fetched_at?: string | null
    message?: string | null
    status: string
    collected_unique_count: number
    successful_request_count: number
    stop_reason?: string | null
  }) => {
    const stop = response.stop_reason ? ` Stop reason: ${response.stop_reason}.` : ''
    setMessage(response.message ?? `Review operation ${response.status}; ${response.successful_request_count} upstream request(s).${stop}`)
    setReviewOperationNotice({
      kind: 'success',
      text: `${operation} ${response.status}: ${response.collected_unique_count} new review(s), ${response.reviews.length} stored review(s), ${response.topics?.length ?? 0} topic(s), and ${response.successful_request_count} upstream request(s).${stop}`
    })
    setSemanticResponse(null)
    setFilterError(null)
    queryClient.invalidateQueries({ queryKey: ['reviews', selectedPlace?.google_place_id] })
    queryClient.invalidateQueries({ queryKey: ['providerUsage'] })
  }

  const syncMutation = useMutation({
    mutationFn: (confirm: boolean) => syncReviews(selectedPlace!.google_place_id, confirm),
    onMutate: () => setReviewOperationNotice({ kind: 'pending', text: 'Fetching and saving reviews…' }),
    onSuccess: (response) => applyReviewSyncResponse('Sync', response),
    onError: (error) => {
      const text = error instanceof Error ? error.message : 'Sync failed'
      setReviewOperationNotice({ kind: 'error', text: `Sync failed: ${text}` })
      handleCostConfirmation(error, 'Sync failed', (confirm) => syncMutation.mutate(confirm))
    }
  })

  const refreshMutation = useMutation({
    mutationFn: (confirm: boolean) => refreshReviews(selectedPlace!.google_place_id, confirm),
    onMutate: () => setReviewOperationNotice({ kind: 'pending', text: 'Refreshing reviews from SerpApi…' }),
    onSuccess: (response) => applyReviewSyncResponse('Refresh', response),
    onError: (error) => {
      const text = error instanceof Error ? error.message : 'Refresh failed'
      setReviewOperationNotice({ kind: 'error', text: `Refresh failed: ${text}` })
      handleCostConfirmation(error, 'Refresh failed', (confirm) => refreshMutation.mutate(confirm), 'Continue with refresh?')
    }
  })

  const filterMutation = useMutation({
    mutationFn: (overrides?: { contentFilter?: string | null; reviewerLabel?: string | null; sort?: ReviewSort }) => {
      if (!selectedPlace) throw new Error('Select a restaurant first')
      const content = overrides?.contentFilter !== undefined ? overrides.contentFilter : filterText
      const name = overrides?.reviewerLabel !== undefined ? overrides.reviewerLabel : reviewerLabel
      const sort = overrides?.sort ?? reviewSort
      return filterReviews(selectedPlace.google_place_id, {
        rating: exactRating ? Number(exactRating) : null,
        reviewer_label: name || null,
        content_filter: content?.trim() || null,
        sort
      })
    },
    onSuccess: (response) => {
      setSemanticResponse(response)
      setFilterError(null)
      setMessage(`Filter matched ${response.filtered_total} review(s).`)
    },
    onError: (error) => {
      setFilterError('Couldn’t apply the new filter; showing previous results. Retry when the local model is available.')
      setMessage(error instanceof Error ? error.message : 'Filter failed')
    }
  })

  const handleCostConfirmation = (
    error: unknown,
    fallback: string,
    retry: (confirm: boolean) => void,
    prompt = 'Continue?'
  ) => {
    const text = error instanceof Error ? error.message : fallback
    setMessage(text)
    if (text.includes('confirm_cost=true')) {
      const ok = window.confirm(`${text}\n\n${prompt}`)
      if (ok) retry(true)
    }
  }

  const effectiveReviewResponse = semanticResponse ?? reviewsQuery.data
  const visibleReviews = effectiveReviewResponse?.reviews ?? []

  const applyFilterIfActive = (overrides?: { contentFilter?: string | null; reviewerLabel?: string | null; sort?: ReviewSort }) => {
    const content = overrides?.contentFilter !== undefined ? overrides.contentFilter : semanticResponse?.content_filter ?? null
    const name = overrides?.reviewerLabel !== undefined ? overrides.reviewerLabel : reviewerLabel
    if ((content?.trim() || name) && selectedPlace) filterMutation.mutate(overrides)
    else {
      setSemanticResponse(null)
      setFilterError(null)
    }
  }

  const setReviewSort = (value: ReviewSort) => {
    setReviewSortState(value)
    if (semanticResponse || reviewerLabel) applyFilterIfActive({ sort: value })
  }

  const setReviewerLabel = (value: string) => {
    setReviewerLabelState(value)
    setSemanticResponse(null)
    setFilterError(null)
    applyFilterIfActive({ reviewerLabel: value })
  }

  const submitSearch = useCallback(
    (event?: React.FormEvent<HTMLFormElement>) => {
      event?.preventDefault()
      if (searchQuery.trim()) searchMutation.mutate({ query: searchQuery.trim() })
    },
    [searchMutation, searchQuery]
  )

  const resetToLanding = () => {
    setMode('landing')
    setMobilePane('results')
    pushHistoryView('landing')
    setSelectedPlace(null)
    setSelectedSearchResult(null)
    setFilterText('')
    setExactRating('')
    setReviewSortState('recent')
    setReviewerLabelState('')
    setSemanticResponse(null)
    setFilterError(null)
    setReviewOperationNotice(null)
    setSearchQuery('')
    setSearchResults([])
    setNextSearchPageToken(null)
    setMessage(null)
  }

  const mobileBack = () => {
    if (searchResults.length) {
      setMode('workspace')
      setMobilePane('results')
    } else {
      setMode('landing')
      setMobilePane('results')
    }
    if (window.history.state?.rrView === 'reviews') window.history.back()
  }

  return (
    <main className="app-shell min-h-screen bg-[#F7F4EE] text-[#24313A]">
      <AppChrome
        mode={mode}
        developerButtonRef={developerButtonRef}
        onDeveloperOpen={() => setDeveloperOpen(true)}
        onNewSearch={resetToLanding}
      />

      {mode === 'landing' ? (
        <SearchLanding
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          onSubmit={submitSearch}
          onAutocompleteSelected={(selection) => autocompleteSelection.mutate(selection)}
          isSearching={searchMutation.isPending}
          message={message}
        />
      ) : (
        <Workspace
          mobilePane={mobilePane}
          setMobilePane={setMobilePane}
          onMobileBack={mobileBack}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          onSubmit={submitSearch}
          isSearching={searchMutation.isPending}
          onAutocompleteSelected={(selection) => autocompleteSelection.mutate(selection)}
          searchResults={searchResults}
          selectedPlace={selectedPlace}
          selectedSearchResult={selectedSearchResult}
          nextSearchPageToken={nextSearchPageToken}
          onLoadNext={() => searchMutation.mutate({ query: searchQuery.trim(), pageToken: nextSearchPageToken })}
          onSelectResult={(result) => selectSearchResult.mutate(result)}
          message={message}
          reviewsQuery={reviewsQuery}
          visibleReviews={visibleReviews}
          filterText={filterText}
          setFilterText={setFilterText}
          exactRating={exactRating}
          setExactRating={(value) => {
            setExactRating(value)
            setSemanticResponse(null)
            setFilterError(null)
          }}
          reviewSort={reviewSort}
          setReviewSort={setReviewSort}
          reviewerLabel={reviewerLabel}
          setReviewerLabel={setReviewerLabel}
          reviewerLabelOptions={filterOptionsQuery.data?.reviewer_label_options ?? []}
          syncPending={syncMutation.isPending}
          refreshPending={refreshMutation.isPending}
          reviewOperationNotice={reviewOperationNotice}
          onSync={() => syncMutation.mutate(false)}
          onRefresh={() => refreshMutation.mutate(false)}
          filterPending={filterMutation.isPending}
          onFilter={(filterTextOverride) => filterMutation.mutate({ contentFilter: filterTextOverride ?? filterText })}
          onResetReviewControls={() => {
            setFilterText('')
            setExactRating('')
            setReviewSortState('recent')
            setReviewerLabelState('')
            setSemanticResponse(null)
            setFilterError(null)
          }}
          filterError={filterError}
          effectiveTotal={effectiveReviewResponse?.total ?? 0}
          effectiveFilteredTotal={effectiveReviewResponse?.filtered_total ?? 0}
        />
      )}

      <DeveloperDrawer
        open={developerOpen}
        usage={usageQuery.data ?? []}
        loading={usageQuery.isLoading || usageQuery.isFetching}
        onRefresh={() => usageQuery.refetch()}
        onClose={() => {
          setDeveloperOpen(false)
          requestAnimationFrame(() => developerButtonRef.current?.focus())
        }}
      />
    </main>
  )
}

export default App
