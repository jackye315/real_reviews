import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useMemo, useRef, useState } from 'react'
import { AppChrome } from './components/AppChrome'
import { DeveloperDrawer } from './components/DeveloperDrawer'
import { SearchLanding } from './components/SearchLanding'
import { Workspace } from './components/Workspace'
import {
  filterReviews,
  getProviderUsage,
  getReviews,
  persistSearchResult,
  persistSelection,
  refreshReviews,
  searchRestaurants,
  syncReviews
} from './lib/api'
import { filterByMinimumRating } from './lib/reviews'
import { useUserLocation } from './hooks/useUserLocation'
import type { PlaceResponse, RestaurantSearchResult, Review, ReviewTopic } from './types/api'
import type { MobilePane, WorkspaceMode } from './types/ui'

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
  const [minRating, setMinRating] = useState('')
  const [selectedReviewIds, setSelectedReviewIds] = useState<string[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const reviewsQuery = useQuery({
    queryKey: ['reviews', selectedPlace?.google_place_id],
    queryFn: () => getReviews(selectedPlace!.google_place_id),
    enabled: Boolean(selectedPlace)
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
    setSelectedReviewIds(null)
    queryClient.invalidateQueries({ queryKey: ['reviews', place.google_place_id] })
  }, [queryClient])

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
      if (!variables.pageToken) {
        setSelectedPlace(null)
        setSelectedSearchResult(null)
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

  const applyReviewSyncResponse = (response: {
    reviews: Review[]
    topics?: ReviewTopic[]
    topics_fetched_at?: string | null
    message?: string | null
    status: string
    successful_request_count: number
    stop_reason?: string | null
  }) => {
    const stop = response.stop_reason ? ` Stop reason: ${response.stop_reason}.` : ''
    setMessage(response.message ?? `Review operation ${response.status}; ${response.successful_request_count} upstream request(s).${stop}`)
    queryClient.setQueryData(['reviews', selectedPlace?.google_place_id], {
      reviews: response.reviews,
      total: response.reviews.length,
      topics: response.topics ?? [],
      topics_fetched_at: response.topics_fetched_at ?? null
    })
    queryClient.invalidateQueries({ queryKey: ['providerUsage'] })
  }

  const syncMutation = useMutation({
    mutationFn: (confirm: boolean) => syncReviews(selectedPlace!.google_place_id, confirm),
    onSuccess: applyReviewSyncResponse,
    onError: (error) => handleCostConfirmation(error, 'Sync failed', (confirm) => syncMutation.mutate(confirm))
  })

  const refreshMutation = useMutation({
    mutationFn: (confirm: boolean) => refreshReviews(selectedPlace!.google_place_id, confirm),
    onSuccess: applyReviewSyncResponse,
    onError: (error) => handleCostConfirmation(error, 'Refresh failed', (confirm) => refreshMutation.mutate(confirm), 'Continue with refresh?')
  })

  const filterMutation = useMutation({
    mutationFn: (filterTextOverride?: string) => filterReviews(filterTextOverride ?? filterText, reviewsQuery.data?.reviews ?? []),
    onSuccess: (ids) => {
      setSelectedReviewIds(ids)
      setMessage(`Filter matched ${ids.length} review(s).`)
    },
    onError: (error) => {
      setSelectedReviewIds(null)
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

  const visibleReviews = useMemo(() => {
    const reviews = reviewsQuery.data?.reviews ?? []
    const ratingFloor = minRating ? Number(minRating) : null
    const ratingFiltered = filterByMinimumRating(reviews, ratingFloor)
    if (!selectedReviewIds) return ratingFiltered
    const allowed = new Set(selectedReviewIds)
    return ratingFiltered.filter((review) => allowed.has(review.id))
  }, [minRating, reviewsQuery.data?.reviews, selectedReviewIds])

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
    setSelectedPlace(null)
    setSelectedSearchResult(null)
    setSearchResults([])
    setNextSearchPageToken(null)
    setSelectedReviewIds(null)
    setMessage(null)
  }

  return (
    <main className="min-h-screen bg-[#F7F4EE] text-[#24313A]">
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
          minRating={minRating}
          setMinRating={setMinRating}
          selectedReviewIds={selectedReviewIds}
          setSelectedReviewIds={setSelectedReviewIds}
          syncPending={syncMutation.isPending}
          refreshPending={refreshMutation.isPending}
          onSync={() => syncMutation.mutate(false)}
          onRefresh={() => refreshMutation.mutate(false)}
          filterPending={filterMutation.isPending}
          onFilter={(filterTextOverride) => filterMutation.mutate(filterTextOverride)}
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
