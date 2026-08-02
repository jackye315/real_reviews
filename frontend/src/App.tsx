import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef, useState } from 'react'
import { AppChrome } from './components/AppChrome'
import { DeveloperDrawer } from './components/DeveloperDrawer'
import { SearchLanding } from './components/SearchLanding'
import { Workspace } from './components/Workspace'
import {
  cancelProviderOperation,
  checkForNewReviews,
  getLoadMoreOptions,
  getRestaurantDetail,
  loadMoreReviews,
  filterReviews,
  getProviderOperation,
  getProviderOperations,
  getProviderUsage,
  getReviewFilterOptions,
  getReviewerContext,
  getReviewerComparison,
  startReviewerContext,
  deleteReviewerContext,
  getReviews,
  persistSearchResult,
  persistSelection,
  newIdempotencyKey,
  refreshReviews,
  searchRestaurants,
  syncReviews
} from './lib/api'
import { useUserLocation } from './hooks/useUserLocation'
import type { PlaceResponse, ProviderOperation, RestaurantSearchResult, ReviewFilterResponse, ReviewerContext, ReviewSort, ReviewSyncResponse } from './types/api'
import type { MobilePane, ReviewOperationNotice, WorkspaceMode } from './types/ui'

type ReviewerRoute = { reviewerId: string; reviewId: string }
type HistoryView = 'landing' | 'results' | 'reviews' | 'reviewer'

function locationRoute(): { placeId: string; reviewerRoute: ReviewerRoute | null } | null {
  const match = window.location.pathname.match(/^\/restaurants\/([^/]+)$/)
  if (!match) return null
  const params = new URLSearchParams(window.location.search)
  const reviewerId = params.get('reviewer')
  const reviewId = params.get('review')
  return { placeId: decodeURIComponent(match[1]), reviewerRoute: reviewerId && reviewId ? { reviewerId, reviewId } : null }
}

function routeUrl(view: HistoryView, placeId?: string, reviewerRoute?: ReviewerRoute | null) {
  if ((view === 'reviews' || view === 'reviewer') && placeId) {
    const path = `/restaurants/${encodeURIComponent(placeId)}`
    return view === 'reviewer' && reviewerRoute ? `${path}?reviewer=${encodeURIComponent(reviewerRoute.reviewerId)}&review=${encodeURIComponent(reviewerRoute.reviewId)}` : path
  }
  return '/'
}

function App() {
  const queryClient = useQueryClient()
  const reviewerContextEnabled = import.meta.env.VITE_REVIEWER_CONTEXT_ENABLED !== 'false'
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
  const [activeProviderOperation, setActiveProviderOperation] = useState<ProviderOperation | null>(null)
  const [loadMoreRecovery, setLoadMoreRecovery] = useState<ProviderOperation | null>(null)
  const [reviewerRoute, setReviewerRoute] = useState<ReviewerRoute | null>(null)
  const [reviewerTimeWindow, setReviewerTimeWindow] = useState<'six_months' | 'one_year' | 'two_years' | 'all_observed'>('two_years')
  const reviewPaneRef = useRef<HTMLElement | null>(null)
  const selectedPlaceRef = useRef<PlaceResponse | null>(null)
  const reviewScrollTopRef = useRef(0)
  const reviewerSourceRef = useRef<HTMLButtonElement | null>(null)
  const reviewSortDefaultedPlaceRef = useRef<string | null>(null)

  const pushHistoryView = useCallback((rrView: HistoryView, placeId?: string, route?: ReviewerRoute | null) => {
    const url = routeUrl(rrView, placeId, route)
    if (window.history.state?.rrView !== rrView || window.location.pathname + window.location.search !== url) {
      window.history.pushState({ rrView, placeId, reviewerRoute: route ?? null }, '', url)
    }
  }, [])

  useEffect(() => {
    selectedPlaceRef.current = selectedPlace
  }, [selectedPlace])

  const restoreRoute = useCallback(async () => {
    const route = locationRoute()
    if (!route) {
      setReviewerRoute(null)
      const view = window.history.state?.rrView as HistoryView | undefined
      if (view === 'results') {
        setMode('workspace')
        setMobilePane('results')
      } else {
        setMode('landing')
        setMobilePane('results')
      }
      return
    }
    setMode('workspace')
    setMobilePane('reviews')
    setReviewerRoute(route.reviewerRoute)
    if (selectedPlaceRef.current?.google_place_id === route.placeId) return
    try {
      const detail = await getRestaurantDetail(route.placeId)
      setSelectedPlace(detail.place)
      setSelectedSearchResult(null)
    } catch (error) {
      setReviewerRoute(null)
      setMessage(error instanceof Error ? error.message : 'Could not restore this restaurant.')
    }
  }, [])

  useEffect(() => {
    const route = locationRoute()
    window.history.replaceState({ rrView: route?.reviewerRoute ? 'reviewer' : route ? 'reviews' : 'landing', placeId: route?.placeId, reviewerRoute: route?.reviewerRoute ?? null }, '', window.location.href)
    void restoreRoute()
    window.addEventListener('popstate', restoreRoute)
    return () => window.removeEventListener('popstate', restoreRoute)
  }, [restoreRoute])

  const savedReviewsQuery = useInfiniteQuery({
    queryKey: ['reviews', selectedPlace?.google_place_id, exactRating, reviewSort],
    queryFn: ({ pageParam }) => getReviews(selectedPlace!.google_place_id, exactRating ? Number(exactRating) : null, reviewSort, 20, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: Boolean(selectedPlace),
    placeholderData: keepPreviousData
  })
  const relevanceAvailable = savedReviewsQuery.data?.pages[0]?.relevance_available
  const reviewsQuery = {
    data: savedReviewsQuery.data ? { ...savedReviewsQuery.data.pages[0], reviews: savedReviewsQuery.data.pages.flatMap((page) => page.reviews) } : undefined,
    isLoading: savedReviewsQuery.isLoading
  }

  useEffect(() => {
    if (!selectedPlace || relevanceAvailable === undefined || reviewSortDefaultedPlaceRef.current === selectedPlace.google_place_id) return
    reviewSortDefaultedPlaceRef.current = selectedPlace.google_place_id
    setReviewSortState(relevanceAvailable ? 'relevant' : 'recent')
  }, [selectedPlace, relevanceAvailable])

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

  const loadMoreOptionsQuery = useQuery({
    queryKey: ['loadMoreOptions', selectedPlace?.google_place_id],
    queryFn: () => getLoadMoreOptions(selectedPlace!.google_place_id),
    enabled: Boolean(selectedPlace && reviewsQuery.data?.total)
  })

  const operationsQuery = useQuery({
    queryKey: ['providerOperations'],
    queryFn: getProviderOperations,
    enabled: developerOpen
  })

  const reviewerContextQuery = useQuery({
    queryKey: ['reviewerContext', reviewerRoute?.reviewerId, reviewerRoute?.reviewId],
    queryFn: () => getReviewerContext(reviewerRoute!.reviewerId, reviewerRoute!.reviewId),
    enabled: Boolean(reviewerRoute)
  })

  const reviewerComparisonQuery = useQuery({
    queryKey: ['reviewerComparison', reviewerRoute?.reviewerId, reviewerRoute?.reviewId, reviewerTimeWindow, 'exact_type'],
    queryFn: () => getReviewerComparison(reviewerRoute!.reviewerId, reviewerRoute!.reviewId, reviewerTimeWindow, 'exact_type'),
    enabled: Boolean(reviewerRoute && reviewerContextQuery.data?.reviewer.context_generation && reviewerTimeWindow !== 'two_years')
  })

  const activeExactComparison = reviewerTimeWindow === 'two_years'
    ? reviewerContextQuery.data?.comparison
    : reviewerComparisonQuery.data
  const reviewerBroaderComparisonQuery = useQuery({
    queryKey: ['reviewerComparison', reviewerRoute?.reviewerId, reviewerRoute?.reviewId, reviewerTimeWindow, 'comparison_family'],
    queryFn: () => getReviewerComparison(reviewerRoute!.reviewerId, reviewerRoute!.reviewId, reviewerTimeWindow, 'comparison_family'),
    enabled: Boolean(
      reviewerRoute
      && reviewerContextQuery.data?.reviewer.context_generation
      && reviewerTimeWindow !== 'two_years'
      && activeExactComparison
      && activeExactComparison.sample_size < 5
    )
  })

  const reviewerContextMutation = useMutation({
    mutationFn: ({ force, confirm }: { force: boolean; confirm: boolean }) => startReviewerContext(reviewerRoute!.reviewerId, reviewerRoute!.reviewId, confirm, force, newIdempotencyKey()),
    onSuccess: (result) => {
      if ('reviewer' in result) queryClient.invalidateQueries({ queryKey: ['reviewerContext', reviewerRoute?.reviewerId, reviewerRoute?.reviewId] })
      else setActiveProviderOperation(result)
    },
    onError: (error) => {
      const text = error instanceof Error ? error.message : 'Could not analyze reviewer history.'
      if (text.includes('confirm_cost=true') && window.confirm(`${text}\n\nContinue?`)) reviewerContextMutation.mutate({ force: true, confirm: true })
    }
  })

  const deleteReviewerContextMutation = useMutation({
    mutationFn: () => deleteReviewerContext(reviewerRoute!.reviewerId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['reviewerContext', reviewerRoute?.reviewerId, reviewerRoute?.reviewId] })
  })

  useEffect(() => {
    const stored = sessionStorage.getItem('real-reviews:active-provider-operation')
    if (!stored) return
    try {
      const value = JSON.parse(stored) as { operationId?: string; placeId?: string }
      if (value.operationId) getProviderOperation(value.operationId).then(setActiveProviderOperation).catch(() => sessionStorage.removeItem('real-reviews:active-provider-operation'))
    } catch {
      sessionStorage.removeItem('real-reviews:active-provider-operation')
    }
  }, [])

  useEffect(() => {
    if (!activeProviderOperation || !['reserved', 'running'].includes(activeProviderOperation.status)) return
    let cancelled = false
    let delay = 2000
    let timer: number | undefined
    const poll = async () => {
      try {
        const operation = await getProviderOperation(activeProviderOperation.operation_id)
        if (cancelled) return
        setActiveProviderOperation(operation)
        if (['completed', 'failed', 'expired', 'cancelled'].includes(operation.status)) {
          sessionStorage.removeItem('real-reviews:active-provider-operation')
          if (operation.place_id) sessionStorage.removeItem(`real-reviews:${operation.operation_type}:${operation.place_id}:idempotency-key`)
          if (operation.status === 'completed') {
            queryClient.invalidateQueries({ queryKey: ['reviews', operation.place_id] })
            queryClient.invalidateQueries({ queryKey: ['loadMoreOptions', operation.place_id] })
            queryClient.invalidateQueries({ queryKey: ['providerUsage'] })
            if (operation.reviewer_id && operation.reviewer_context) {
              queryClient.setQueryData(['reviewerContext', operation.reviewer_id, operation.reviewer_context.current.review.id], operation.reviewer_context)
            } else if (operation.reviewer_id) queryClient.invalidateQueries({ queryKey: ['reviewerContext', operation.reviewer_id] })
          }
          if (operation.error_code === 'PROVIDER_CURSOR_EXPIRED') setLoadMoreRecovery(operation)
          setReviewOperationNotice({
            kind: operation.status === 'completed' ? 'success' : 'error',
            text: operation.status === 'expired'
              ? 'The previous provider attempt expired before completion. Its unused reservation was released; try Refresh again.'
              : `Provider operation ${operation.status}${operation.stop_reason ? `: ${operation.stop_reason}` : '.'}`
          })
          return
        }
        delay = Math.min(5000, delay + 1000)
        timer = window.setTimeout(poll, delay)
      } catch {
        timer = window.setTimeout(poll, delay)
      }
    }
    timer = window.setTimeout(poll, delay)
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [activeProviderOperation, queryClient])

  const openWorkspaceWithPlace = useCallback((place: PlaceResponse, sourceResult: RestaurantSearchResult | null = null) => {
    setSelectedPlace(place)
    setSelectedSearchResult(sourceResult)
    setMode('workspace')
    setMobilePane('reviews')
    setFilterText('')
    setExactRating('')
    setReviewSortState('recent')
    reviewSortDefaultedPlaceRef.current = null
    setReviewerLabelState('')
    setSemanticResponse(null)
    setFilterError(null)
    setReviewOperationNotice(null)
    setReviewerRoute(null)
    pushHistoryView('reviews', place.google_place_id)
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
        setReviewerRoute(null)
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

  const applyReviewSyncResponse = (operation: 'Sync' | 'Refresh', response: ReviewSyncResponse) => {
    const stop = response.stop_reason ? ` Stop reason: ${response.stop_reason}.` : ''
    setReviewOperationNotice({
      kind: 'success',
      text: response.status === 'cached'
        ? `Using ${response.reviews.length} saved review(s). No provider request was made.`
        : `${operation} ${response.status}: ${response.collected_unique_count} new review(s), ${response.reviews.length} stored review(s), and ${response.successful_request_count} upstream request(s).${stop}`
    })
    setSemanticResponse(null)
    setFilterError(null)
    setActiveProviderOperation(null)
    sessionStorage.removeItem('real-reviews:active-provider-operation')
    queryClient.invalidateQueries({ queryKey: ['reviews', selectedPlace?.google_place_id] })
    queryClient.invalidateQueries({ queryKey: ['loadMoreOptions', selectedPlace?.google_place_id] })
    queryClient.invalidateQueries({ queryKey: ['providerUsage'] })
    queryClient.invalidateQueries({ queryKey: ['providerOperations'] })
  }

  const terminalOperation = (operation: ProviderOperation, kind: 'sync' | 'refresh') => {
    clearKey(kind)
    setActiveProviderOperation(null)
    sessionStorage.removeItem('real-reviews:active-provider-operation')
    setReviewOperationNotice({
      kind: operation.status === 'completed' ? 'success' : 'error',
      text: operation.status === 'expired'
        ? 'The previous provider attempt expired before completion. Its unused reservation was released; try Refresh again.'
        : `Provider operation ${operation.status}${operation.stop_reason ? `: ${operation.stop_reason}` : '.'}`
    })
    if (operation.status === 'completed') {
      queryClient.invalidateQueries({ queryKey: ['reviews', operation.place_id] })
      queryClient.invalidateQueries({ queryKey: ['loadMoreOptions', operation.place_id] })
      queryClient.invalidateQueries({ queryKey: ['providerUsage'] })
      queryClient.invalidateQueries({ queryKey: ['providerOperations'] })
    }
  }

  const retainOperation = (operation: ProviderOperation, key: string) => {
    setActiveProviderOperation(operation)
    sessionStorage.setItem('real-reviews:active-provider-operation', JSON.stringify({ operationId: operation.operation_id, key, placeId: operation.place_id }))
    setReviewOperationNotice({
      kind: 'pending',
      text: operation.cancel_requested_at ? 'Cancellation requested…' : `Provider operation ${operation.status}; checking again shortly.`
    })
  }

  const operationKey = (kind: 'sync' | 'refresh' | 'load_more' | 'check_new') => `real-reviews:${kind}:${selectedPlace?.google_place_id ?? ''}:idempotency-key`
  const keyFor = (kind: 'sync' | 'refresh' | 'load_more' | 'check_new') => sessionStorage.getItem(operationKey(kind)) ?? newIdempotencyKey()
  const rememberKey = (kind: 'sync' | 'refresh' | 'load_more' | 'check_new', key: string) => sessionStorage.setItem(operationKey(kind), key)
  const clearKey = (kind: 'sync' | 'refresh' | 'load_more' | 'check_new') => sessionStorage.removeItem(operationKey(kind))

  const syncMutation = useMutation({
    mutationFn: ({ confirm, key }: { confirm: boolean; key: string }) => syncReviews(selectedPlace!.google_place_id, confirm, key),
    onMutate: ({ key }) => {
      rememberKey('sync', key)
      setReviewOperationNotice({ kind: 'pending', text: 'Fetching and saving reviews…' })
    },
    onSuccess: (response, variables) => {
      if ('reviews' in response) {
        clearKey('sync')
        applyReviewSyncResponse('Sync', response)
      } else if (['completed', 'failed', 'expired', 'cancelled'].includes(response.status)) {
        terminalOperation(response, 'sync')
      } else retainOperation(response, variables.key)
    },
    onError: (error, variables) => {
      const text = error instanceof Error ? error.message : 'Sync failed'
      setReviewOperationNotice({ kind: 'error', text: `Sync failed: ${text}` })
      handleCostConfirmation(error, 'Sync failed', (confirm) => syncMutation.mutate({ confirm, key: variables.key }))
    }
  })

  const refreshMutation = useMutation({
    mutationFn: ({ confirm, key }: { confirm: boolean; key: string }) => refreshReviews(selectedPlace!.google_place_id, confirm, key),
    onMutate: ({ key }) => {
      rememberKey('refresh', key)
      setReviewOperationNotice({ kind: 'pending', text: 'Refreshing relevance from SerpApi…' })
    },
    onSuccess: (response, variables) => {
      if ('reviews' in response) {
        clearKey('refresh')
        applyReviewSyncResponse('Refresh', response)
      } else if (['completed', 'failed', 'expired', 'cancelled'].includes(response.status)) {
        terminalOperation(response, 'refresh')
      } else retainOperation(response, variables.key)
    },
    onError: (error, variables) => {
      const text = error instanceof Error ? error.message : 'Refresh failed'
      setReviewOperationNotice({ kind: 'error', text: `Refresh failed: ${text}` })
      handleCostConfirmation(error, 'Refresh failed', (confirm) => refreshMutation.mutate({ confirm, key: variables.key }), 'Continue with refresh?')
    }
  })

  const checkNewMutation = useMutation({
    mutationFn: ({ confirm, key }: { confirm: boolean; key: string }) => checkForNewReviews(selectedPlace!.google_place_id, confirm, key),
    onMutate: ({ key }) => {
      rememberKey('check_new', key)
      setReviewOperationNotice({ kind: 'pending', text: 'Checking for new reviews from SerpApi…' })
    },
    onSuccess: (response, variables) => {
      if ('reviews' in response) {
        clearKey('check_new')
        applyReviewSyncResponse('Refresh', response)
      } else retainOperation(response, variables.key)
    },
    onError: (error, variables) => {
      const text = error instanceof Error ? error.message : 'Check for new reviews failed'
      setReviewOperationNotice({ kind: 'error', text: `Check for new reviews failed: ${text}` })
      handleCostConfirmation(error, 'Check for new reviews failed', (confirm) => checkNewMutation.mutate({ confirm, key: variables.key }), 'Continue with newest-first reconciliation?')
    }
  })

  const loadMoreMutation = useMutation({
    mutationFn: ({ target, restart, confirm, key }: { target: 20 | 50 | 100; restart: boolean; confirm: boolean; key: string }) => loadMoreReviews(selectedPlace!.google_place_id, target, restart, confirm, key),
    onMutate: ({ key }) => {
      rememberKey('load_more', key)
      setReviewOperationNotice({ kind: 'pending', text: 'Fetching older reviews from SerpApi…' })
    },
    onSuccess: (operation, variables) => retainOperation(operation, variables.key),
    onError: (error, variables) => {
      const text = error instanceof Error ? error.message : 'Fetch older reviews failed'
      setReviewOperationNotice({ kind: 'error', text: `Fetch older reviews failed: ${text}` })
      handleCostConfirmation(error, 'Fetch older reviews failed', (confirm) => loadMoreMutation.mutate({ ...variables, confirm }))
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
    },
    onError: (error) => {
      setFilterError(error instanceof Error
        ? `Couldn’t apply the new filter: ${error.message}`
        : 'Couldn’t apply the new filter; showing previous results. Retry when the local model is available.')
    }
  })

  const handleCostConfirmation = (
    error: unknown,
    fallback: string,
    retry: (confirm: boolean) => void,
    prompt = 'Continue?'
  ) => {
    const text = error instanceof Error ? error.message : fallback
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
    setReviewerRoute(null)
    setSearchQuery('')
    setSearchResults([])
    setNextSearchPageToken(null)
    setMessage(null)
  }

  const cancelActiveProviderOperation = () => {
    if (!activeProviderOperation) return
    cancelProviderOperation(activeProviderOperation.operation_id)
      .then((operation) => {
        setActiveProviderOperation(operation)
        setReviewOperationNotice({ kind: 'pending', text: 'Cancellation requested…' })
      })
      .catch((error) => setReviewOperationNotice({
        kind: 'error',
        text: error instanceof Error ? `Couldn’t request cancellation: ${error.message}` : 'Couldn’t request cancellation.'
      }))
  }

  const openReviewer = (reviewerId: string, reviewId: string, source: HTMLButtonElement) => {
    if (!selectedPlace) return
    reviewScrollTopRef.current = reviewPaneRef.current?.scrollTop ?? 0
    reviewerSourceRef.current = source
    const route = { reviewerId, reviewId }
    setReviewerRoute(route)
    setMobilePane('reviews')
    window.history.pushState({ rrView: 'reviewer', placeId: selectedPlace.google_place_id, reviewerRoute: route, reviewerFromReviews: true }, '', routeUrl('reviewer', selectedPlace.google_place_id, route))
  }

  const closeReviewer = () => {
    if (window.history.state?.rrView === 'reviewer' && window.history.state?.reviewerFromReviews) {
      window.history.back()
      return
    }
    if (selectedPlace) window.history.replaceState({ rrView: 'reviews', placeId: selectedPlace.google_place_id, reviewerRoute: null }, '', routeUrl('reviews', selectedPlace.google_place_id))
    setReviewerRoute(null)
  }

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      if (reviewerRoute) document.getElementById('reviewer-heading')?.focus()
      else {
        const pane = reviewPaneRef.current
        if (pane && typeof pane.scrollTo === 'function') pane.scrollTo({ top: reviewScrollTopRef.current })
        else if (pane) pane.scrollTop = reviewScrollTopRef.current
        reviewerSourceRef.current?.focus()
        reviewerSourceRef.current = null
      }
    })
    return () => window.cancelAnimationFrame(frame)
  }, [reviewerRoute])

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
          reviewerRoute={reviewerRoute}
          reviewerContext={reviewerContextQuery.data ? (
            reviewerTimeWindow === 'two_years'
              ? reviewerContextQuery.data
              : activeExactComparison
                ? { ...reviewerContextQuery.data, comparison: activeExactComparison, broader_comparison: reviewerBroaderComparisonQuery.data ?? null } as ReviewerContext
                : { ...reviewerContextQuery.data, comparison: null, broader_comparison: null } as ReviewerContext
          ) : undefined}
          reviewerContextLoading={reviewerContextQuery.isLoading || reviewerContextMutation.isPending}
          reviewerContextError={reviewerContextQuery.error instanceof Error ? reviewerContextQuery.error.message : null}
          reviewerTimeWindow={reviewerTimeWindow}
          onReviewerTimeWindowChange={setReviewerTimeWindow}
          onOpenReviewer={reviewerContextEnabled ? openReviewer : undefined}
          onCloseReviewer={closeReviewer}
          onAnalyzeReviewer={() => reviewerContextMutation.mutate({ force: false, confirm: false })}
          onRefreshReviewer={() => reviewerContextMutation.mutate({ force: true, confirm: false })}
          onDeleteReviewer={() => { if (window.confirm('Delete locally retained reviewer context?')) deleteReviewerContextMutation.mutate() }}
          reviewPaneRef={reviewPaneRef}
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
          relevanceAvailable={Boolean(reviewsQuery.data?.relevance_available)}
          syncPending={syncMutation.isPending}
          refreshPending={refreshMutation.isPending}
          checkNewPending={checkNewMutation.isPending}
          reviewOperationNotice={reviewOperationNotice}
          activeProviderOperation={activeProviderOperation}
          onSync={() => syncMutation.mutate({ confirm: false, key: keyFor('sync') })}
          onRefresh={() => refreshMutation.mutate({ confirm: false, key: keyFor('refresh') })}
          onCheckNew={() => checkNewMutation.mutate({ confirm: false, key: keyFor('check_new') })}
          onCancelProviderOperation={cancelActiveProviderOperation}
          savedHasMore={Boolean(!semanticResponse && savedReviewsQuery.hasNextPage)}
          savedMorePending={savedReviewsQuery.isFetchingNextPage}
          onShowMoreSaved={() => savedReviewsQuery.fetchNextPage()}
          loadMoreChoices={loadMoreOptionsQuery.data?.choices ?? []}
          loadMorePending={loadMoreMutation.isPending}
          loadMoreRecovery={loadMoreRecovery}
          onFetchOlder={(target, restart = false) => loadMoreMutation.mutate({ target, restart, confirm: false, key: newIdempotencyKey() })}
          filterPending={filterMutation.isPending}
          onFilter={(filterTextOverride) => filterMutation.mutate({ contentFilter: filterTextOverride ?? filterText })}
          onResetReviewControls={() => {
            setFilterText('')
            setExactRating('')
            setReviewSortState(reviewsQuery.data?.relevance_available ? 'relevant' : 'recent')
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
        operations={operationsQuery.data ?? []}
        loading={usageQuery.isLoading || usageQuery.isFetching || operationsQuery.isLoading || operationsQuery.isFetching}
        onRefresh={() => {
          usageQuery.refetch()
          operationsQuery.refetch()
        }}
        onClose={() => setDeveloperOpen(false)}
      />
    </main>
  )
}

export default App
