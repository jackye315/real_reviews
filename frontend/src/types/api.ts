export type PlaceResponse = {
  id: string
  google_place_id: string
  display_name: string
  formatted_address?: string | null
  latitude?: number | null
  longitude?: number | null
  viewport?: Record<string, unknown> | null
  place_types?: string[] | null
  google_maps_url?: string | null
  llm_dish_summary?: string | null
  created_at: string
  updated_at: string
}

export type RestaurantSearchResult = {
  google_place_id: string
  display_name: string
  formatted_address?: string | null
  latitude?: number | null
  longitude?: number | null
  viewport?: Record<string, unknown> | null
  place_types?: string[] | null
  google_maps_url?: string | null
  rating?: number | null
  user_rating_count?: number | null
  distance_meters?: number | null
}

export type RestaurantSearchPage = {
  results: RestaurantSearchResult[]
  next_page_token?: string | null
}

export type RestaurantDetailResponse = {
  place: PlaceResponse
  stored_review_count: number
  last_fetch_time?: string | null
}

export type DishSummaryResponse = { summary: string }

export type GoogleReviewSummary = {
  status: 'available' | 'unavailable'
  text?: { text: string; language_code?: string | null } | null
  disclosure?: { text: string; language_code?: string | null } | null
  reviews_uri?: string | null
  flag_content_uri?: string | null
  operation: { id: string; settled_units: number }
}

export type ReviewDetailValue = string | number | boolean | Array<string | number | boolean>

export type ReviewImage = {
  url: string
  position: number
  provider: string
}

export type Review = {
  id: string
  rating?: number | null
  text?: string | null
  original_text?: string | null
  publication_timestamp?: string | null
  last_edit_timestamp?: string | null
  canonical_source_url?: string | null
  author_display_name?: string | null
  author_avatar_url?: string | null
  reviewer_id?: string | null
  source_labels: string[]
  details: Record<string, ReviewDetailValue>
  translated_details: Record<string, ReviewDetailValue>
  images: ReviewImage[]
  first_fetched_at: string
  last_seen_at: string
  suspected_duplicate: boolean
}

export type ReviewTopic = {
  provider_topic_id: string
  keyword: string
  mentions?: number | null
  language_code?: string | null
  rank: number
}

export type ReviewSort = 'relevant' | 'recent' | 'oldest' | 'rating_high' | 'rating_low'

export type ReviewerLabelOption = {
  value: string
  label: string
}

export type ReviewFilterOptionsResponse = {
  reviewer_label_options: ReviewerLabelOption[]
}

export type ReviewListResponse = {
  reviews: Review[]
  page_size?: number
  next_cursor?: string | null
  has_more?: boolean
  review_corpus_version?: number
  total: number
  filtered_total: number
  topics: ReviewTopic[]
  topics_fetched_at?: string | null
  relevance_available?: boolean
  relevance_fetched_at?: string | null
  relevance_ranked_count?: number
  relevance_status?: string | null
}

export type ReviewFilterResponse = ReviewListResponse & {
  candidate_count: number
  selected_review_ids: string[]
  skipped_missing_label_count: number
  rating_filter?: number | null
  reviewer_label_filter?: string | null
  content_filter?: string | null
  sort: ReviewSort
  llm_used: boolean
  message?: string | null
}

export type ReviewSyncResponse = {
  place_id: string
  status: string
  collected_unique_count: number
  successful_request_count: number
  operation_id?: string | null
  estimated_request_count?: number
  cached_response_count?: number
  failed_request_count?: number
  uncertain_request_count?: number
  released_reserved_count?: number
  remaining_local_budget?: number | null
  pagination_cursor?: string | null
  stop_reason?: string | null
  reviews: Review[]
  topics: ReviewTopic[]
  topics_fetched_at?: string | null
  fallback_used: boolean
  message?: string | null
}

export type LoadMoreChoice = { provider_record_count: 20 | 50 | 100; estimated_request_count: number; allowed: boolean }
export type LoadMoreOptions = { cursor_available: boolean; active_operation_id?: string | null; remaining_effective_budget: number; account_snapshot_age_seconds?: number | null; choices: LoadMoreChoice[] }

export type ProviderOperation = {
  operation_id: string
  provider: string
  operation_type: string
  provider_sort?: string | null
  place_id?: string | null
  restaurant_name?: string | null
  reviewer_id?: string | null
  reviewer_name?: string | null
  status: 'reserved' | 'running' | 'completed' | 'failed' | 'expired' | 'cancelled'
  estimated_request_count: number
  reserved_request_count: number
  successful_request_count: number
  cached_response_count: number
  failed_request_count: number
  uncertain_request_count: number
  released_reserved_count: number
  collected_unique_count: number
  remaining_local_budget?: number | null
  stop_reason?: string | null
  error_code?: string | null
  recovery_available?: boolean
  recovery_estimated_request_count?: number | null
  cancel_requested_at?: string | null
  created_at: string
  updated_at: string
  completed_at?: string | null
  provider_results_returned?: number | null
  accepted_food_and_drink_count?: number | null
  rejected_non_food_count?: number | null
  rejected_unknown_type_count?: number | null
  rejected_missing_required_data_count?: number | null
  duplicate_result_count?: number | null
  context_generation?: number | null
  reviewer_context?: ReviewerContext | null
}

export type ReviewerRelevantReview = {
  id: string
  place_name: string
  rating: number
  text?: string | null
  original_text?: string | null
  provider_date_text?: string | null
  publication_date_is_approximate: boolean
  source_url?: string | null
}

export type ReviewerComparison = {
  current_rating: number
  match_level: 'exact_type' | 'comparison_family'
  normalized_venue_type?: string | null
  comparison_family?: string | null
  time_window: 'six_months' | 'one_year' | 'two_years' | 'all_observed'
  sample_size: number
  average_rating?: number | null
  median_rating?: number | null
  standard_deviation?: number | null
  difference_from_average?: number | null
  rating_distribution: Record<string, number>
  individual_ratings: number[]
  contains_approximate_dates: boolean
  relevant_reviews?: ReviewerRelevantReview[]
}

export type ReviewerContext = {
  reviewer: { id: string; display_name?: string | null; avatar_url?: string | null; profile_url?: string | null; local_guide?: boolean | null; provider_review_count?: number | null; provider_photo_count?: number | null; level?: number | null; points?: number | null; context_status: string; context_fetched_at?: string | null; context_generation: number; provider_results_returned?: number | null; accepted_food_and_drink_count?: number | null }
  current: { review: Review; restaurant_name: string; restaurant_place_id?: string | null; normalized_venue_type?: string | null; comparison_family?: string | null }
  comparison?: ReviewerComparison | null
  broader_comparison?: ReviewerComparison | null
  active_operation_id?: string | null
  stale: boolean
}

export type ProviderUsage = {
  id: string
  provider: string
  plan_period: string
  operation_type?: string
  successful_request_count: number
  cached_response_count: number
  failed_request_count: number
  updated_at: string
}
