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
  source_labels: string[]
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

export type ReviewSort = 'recent' | 'oldest' | 'rating_high' | 'rating_low'

export type ReviewerLabelOption = {
  value: string
  label: string
}

export type ReviewFilterOptionsResponse = {
  reviewer_label_options: ReviewerLabelOption[]
}

export type ReviewListResponse = {
  reviews: Review[]
  total: number
  filtered_total: number
  topics: ReviewTopic[]
  topics_fetched_at?: string | null
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
  pagination_cursor?: string | null
  stop_reason?: string | null
  reviews: Review[]
  topics: ReviewTopic[]
  topics_fetched_at?: string | null
  fallback_used: boolean
  message?: string | null
}

export type ProviderUsage = {
  id: string
  provider: string
  plan_period: string
  successful_request_count: number
  cached_response_count: number
  failed_request_count: number
  updated_at: string
}
