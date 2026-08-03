# Real Reviews — Backlog

This file is the source of truth for intentionally deferred features and future product ideas. An item listed here is not implemented unless its status says `Done`.

Statuses:

- `Proposed`: captured but not ready for implementation
- `Ready`: sufficiently designed and accepted for implementation
- `In progress`: implementation has started
- `Done`: implemented and verified

## BL-001 — Stop refresh pagination after known unchanged reviews

- Status: `Done`
- Area: Review synchronization and SerpApi cost control
- Priority: High

### Goal

Avoid repeatedly spending the full approximately four SerpApi searches when a newest-first refresh reaches a run of reviews that are already stored and unchanged.

### Intended behavior

- Apply the optimization only to manual newest-first refreshes.
- Do not apply it to the first review sync or to `Load more`, because those operations intentionally collect older reviews.
- Track the trailing number of consecutive reviews that match an existing canonical review and have no material changes.
- Treat text, original text, rating, publication/edit timestamps, structured details, translated details, image URLs, and provider origin fields as material for change detection.
- Reset the streak whenever a new or materially changed review is encountered.
- After processing and persisting a complete fetched page, stop requesting another page when the trailing streak is at least 10.
- Keep 10 as the default threshold, with a configuration option such as `REFRESH_KNOWN_STREAK_LIMIT`.
- Return and record a distinct stop reason such as `known_unchanged_streak`; do not report the run as failed.

### Implementation notes

The repository currently returns only `(review, created)` from review upsert. This feature needs an outcome that distinguishes `created`, `changed`, and `unchanged`. The streak should be evaluated across page boundaries, but the backend should process the entire page already paid for before deciding whether to request another page.

### Implementation update — 2026-07-29

Implemented the manual refresh optimization.

- Added `REFRESH_KNOWN_STREAK_LIMIT`, defaulting to `10`.
- Review upsert now distinguishes `created`, `changed`, and `unchanged` outcomes.
- Manual newest-first refresh tracks trailing known unchanged reviews across page boundaries.
- After processing a complete fetched page, refresh stops before the next provider request when the unchanged streak reaches the configured threshold.
- Initial sync remains unaffected; the optimization is only enabled for refresh without an explicit cursor.
- Sync-run records and API responses now expose `stop_reason`, including `known_unchanged_streak`.
- Added the frontend `Refresh` button and cost-confirmation handling.
- Added backend tests for request estimation and material-change detection.

### Acceptance criteria

- Ten trailing known unchanged reviews prevent the next provider-page request.
- A new review resets the streak.
- An edited or otherwise materially changed review resets the streak.
- A streak may span multiple fetched pages.
- All reviews in an already fetched page are processed and persisted.
- Initial sync and load-more pagination are unaffected.
- Sync-run data and API responses expose the stop reason.
- Tests cover new, changed, unchanged, cross-page, cursor-end, and threshold-disabled cases.

## BL-002 — On-demand reviewer context and rating baseline

- Status: `Done`
- Area: Reviewer context
- Priority: Medium
- Detailed design: [Design document, Section 17](design_doc.md#17-planned-feature-on-demand-reviewer-context)

### Goal

Let the user open a local, no-cost reviewer profile from any stored restaurant review and then explicitly choose whether to fetch that reviewer's public Google Maps contribution history. After history is available, compare the current restaurant rating with the same reviewer's observed ratings for other food-and-drink venues of the same normalized type and selected time window.

This is contextual information, not a credibility, truthfulness, expertise, or quality verdict. The feature must never automatically raise, lower, filter, hide, or reorder a restaurant review. Missing or small comparison samples are unavailable or limited evidence, not a negative signal.

### Verified provider boundary

- A normal SerpApi `google_maps_reviews` restaurant response already includes `user.name`, `user.link`, `user.contributor_id`, `user.thumbnail`, `user.local_guide`, `user.reviews`, and `user.photos`. Save those fields during ordinary restaurant-review ingestion; opening a reviewer profile must not require another provider request.
- The current normalizer persists only part of that metadata. BL-002 must add persistence for at least Local Guide status, provider-reported public review count, and photo count. Historical rows may show the subset already stored until their restaurant is refreshed; the profile GET must not silently enrich them.
- The explicit history action uses `engine=google_maps_contributor_reviews`, the known contributor ID, `hl=en`, and `num=200`.
- SerpApi currently returns at most 200 contributor reviews in one successful response. The result contains top-level contributor metadata and a `reviews` list. A review can contain `review_id`, `rating`, relative `date`, text, details, images, link, and `place_info` with title, address, coordinates, one human-readable `type`, thumbnail, and Maps `data_id`.
- The contributor endpoint does not provide a supported server-side food/restaurant-type filter. Fetch once, classify locally, and persist only allowlisted food-and-drink results.
- One successful uncached contributor lookup counts as one SerpApi search regardless of whether 10 or 200 reviews are returned. Default SerpApi caching remains enabled.
- Provider references: [Google Maps Reviews API](https://serpapi.com/google-maps-reviews-api) and [Google Maps Contributor Reviews API](https://serpapi.com/google-maps-contributor-reviews-api).

### Two-stage user flow

#### Stage 1: local reviewer profile

- Make the reviewer name or a nearby `View reviewer` action a link only when the review is associated with a usable internal reviewer/contributor record.
- Navigate to a real history-backed reviewer route such as `/reviewers/{reviewer_id}?review={current_review_id}`. Use an internal reviewer ID in the public API route rather than exposing a provider identifier as the canonical application key.
- On desktop, replace the right review pane with the reviewer detail surface while retaining the restaurant search/results pane and its scroll state. On phones, use a full-screen reviewer surface. Browser and in-app Back return to the same restaurant and review position.
- `GET` the reviewer profile from PostgreSQL only. Opening, refreshing, or navigating back to this page must never contact Google, SerpApi, or the LLM.
- Initially show the public display name, avatar, Google Maps profile link, Local Guide status, provider-reported public review count, photo count, the current restaurant, and the current review. Missing metadata is shown as unavailable, not fetched automatically.
- Make the distinction between provider totals and locally observed data explicit. For example: `1,031 public Google review contributions`, `200 returned in the saved snapshot`, and `63 supported food-and-drink reviews retained` are three different counts.
- If context has never been fetched, show `Analyze review history — may use 1 SerpApi search`.
- If context is loading, preserve the profile and show an inline progress/skeleton state.
- If context exists, render it immediately from PostgreSQL. Do not call SerpApi merely because the snapshot is old.
- If context is older than the advisory stale interval, continue showing it with `History fetched <date>` and an explicit `Refresh history — may use 1 SerpApi search` action.
- Fall back to the public Google Maps contributor link when local profile data is incomplete or provider enrichment is unavailable.

#### Stage 2: explicit history and comparison

- Clicking `Analyze review history` or `Refresh history` first checks again for a reusable saved snapshot.
- When no reusable result is selected, show the BL-007 preflight/remaining-budget information, disclose an estimate of one search, require confirmation, and submit an idempotent paid operation.
- When the operation completes, update the existing reviewer surface in place. Do not navigate to a second results page.
- Put the comparison summary at the top, followed by disclosed sample counts, rating distribution, optional broader comparison, reviewer metadata, and progressively disclosed relevant accepted reviews with their stored bodies.
- Changing the time window or exact/broader comparison view is a local database calculation and never triggers another provider request.
- Opening the same reviewer from a different restaurant reuses the same saved contributor snapshot and calculates a new local comparison relative to the newly selected restaurant.

Required profile/context states:

```text
not_loaded
loading
available
available_stale
failed
```

### API contract

Use reviewer-scoped APIs while retaining the originating review as comparison context:

```http
GET /api/v1/reviewers/{reviewer_id}?current_review_id={review_id}
```

- PostgreSQL-only and side-effect free.
- Returns public profile metadata already observed during restaurant ingestion, context status/fetch timestamp, provider-versus-retained counts, and the current review summary.
- If a context snapshot exists, it may also include the default two-year exact-type comparison so the page renders with one local request.
- This endpoint must have no provider client call path.
- Validate that `current_review_id` belongs to the requested reviewer and to a supported current place; reject mismatches rather than comparing an arbitrary review/reviewer pair.

```http
GET /api/v1/reviewers/{reviewer_id}/comparison
    ?current_review_id={review_id}
    &time_window=two_years
    &match_level=exact_type
```

- PostgreSQL-only and side-effect free.
- Allowlisted time windows: `six_months`, `one_year`, `two_years`, and `all_observed`; default `two_years`.
- Allowlisted match levels: `exact_type` and `comparison_family`. The frontend defaults to exact type and may offer the broader result only when separately labeled.

```http
POST /api/v1/reviewers/{reviewer_id}/context
Idempotency-Key: <client-generated key>

{
  "current_review_id": "uuid",
  "confirm_cost": true,
  "force_refresh": false
}
```

- Recheck for a reusable snapshot before reserving or contacting the provider.
- A live lookup is a BL-007 asynchronous provider operation with operation type `serpapi_contributor_reviews`, a conservative reservation of one search, the global provider semaphore, an idempotency fingerprint, and a per-contributor concurrency guard.
- Return `202` with the provider operation ID when live work starts. Poll the existing provider-operation status endpoint.
- The terminal operation result includes the saved context summary and the requested default comparison, so the frontend does not need an additional stats request before rendering.
- If `force_refresh=false` and a reusable snapshot already exists, return/replay the saved result without an upstream request and without consuming a budget reservation. A stale snapshot remains reusable for viewing; only explicit `force_refresh=true` may replace it.
- Extend the existing provider-operation record/response with nullable `reviewer_id` and reviewer display summary. Persist only non-raw context counts and the default comparison in operation result metadata; never persist the contributor payload there. The single-operation GET may return the typed comparison result, while the Developer drawer list remains a compact safe summary.
- Enforce one active contributor operation per reviewer across processes by locking the reviewer row during reservation/active-operation creation and applying the existing same-subject collision rule to `reviewer_id`. The process-local provider semaphore alone is not sufficient for duplicate prevention.

```http
DELETE /api/v1/reviewers/{reviewer_id}/context
```

- Deletes locally retained contributor-context state according to the shared-review rules below. It never contacts SerpApi.

Stable reviewer-context errors include:

```text
REVIEWER_NOT_FOUND
REVIEWER_REVIEW_MISMATCH
REVIEWER_CONTRIBUTOR_ID_UNAVAILABLE
REVIEWER_CONTEXT_ALREADY_RUNNING
REVIEWER_CONTEXT_PROVIDER_FAILED
```

Continue reusing BL-007 codes for confirmation, budget, hourly ceiling, idempotency conflict, and cancellation. A successful snapshot with zero accepted or zero exact-type reviews is a valid empty-evidence response, not a provider error.

### Persistent data model

Keep the current canonical `places`, `reviews`, `review_origins`, and `review_images` model. Add only the reviewer and Maps-data-ID relationships needed for shared contributor history; do not introduce a graph database or duplicate restaurant-review and contributor-review tables.

#### `reviewers`

```text
id UUID primary key
google_contributor_id string nullable unique
display_name nullable
avatar_url nullable
profile_url nullable
local_guide nullable
level nullable
points nullable
provider_review_count nullable
provider_rating_count nullable
provider_photo_count nullable
profile_observed_at nullable
context_generation integer not null default 0
context_fetched_at nullable
context_status: not_loaded | available | failed
provider_results_returned integer nullable
accepted_food_and_drink_count integer nullable
rejected_non_food_count integer nullable
rejected_unknown_type_count integer nullable
rejected_missing_required_data_count integer nullable
created_at
updated_at
```

- This table represents public review contributors, not application login accounts.
- Upsert primarily by `google_contributor_id`; provider identifiers remain external identifiers while the internal UUID is the stable application key.
- Ordinary restaurant-review ingestion updates the provider-reported metadata and `profile_observed_at` without fetching contributor history.
- A contributor fetch may add more current `level`, `points`, and contribution totals.
- Configure `REVIEWER_CONTEXT_STALE_AFTER_DAYS`, default `30`, as an advisory UI threshold only. Staleness never causes an automatic refresh.
- Persist only `not_loaded`, `available`, or `failed`. Derive `loading` from an active BL-007 provider operation and derive `available_stale` from `available` plus the advisory age. A failed refresh with an older valid generation remains persistently `available`; the failed operation is separate. Use persistent `failed` only when no valid generation exists.
- Migration/backfill creates one reviewer for each distinct non-null existing `review_origins.contributor_id`, chooses the latest available non-null public profile fields, and links matching reviews. Public review/photo counts remain null until a future restaurant refresh or explicit contributor fetch supplies them. Never merge authors that lack the same exact contributor ID.

#### `place_data_ids`

```text
data_id string primary key
place_id UUID foreign key -> places.id
first_seen_at
last_verified_at
```

- Map a SerpApi/Google Maps `data_id` to the existing canonical place UUID.
- Keep `places.google_place_id` as the official Google identifier when known, but make it nullable for contributor-only observed venues.
- Contributor-only supported venues use a place state such as `observed`; a restaurant selected through normal search becomes `selected` and gains official Google metadata.
- Retain both IDs when known. Do not delete the `data_id` after an official Place ID is discovered.
- An accepted review for an `observed` place may appear immediately inside reviewer context. The observed place does not become an independent main search result or claim a complete restaurant review corpus. If normal search later selects/confirms it, promote/merge it to `selected` and reuse the canonical review already stored.

#### `places` additions

```text
state: observed | selected
provider_type nullable
normalized_venue_type nullable
comparison_family nullable
type_source nullable
type_confidence nullable
classifier_version nullable
```

- Suggested comparison families are `restaurant`, `cafe`, `bar_or_pub`, `brewery_or_winery`, and `bakery_or_dessert`.
- Keep the most specific supported normalized type for exact comparisons, for example `pizza_restaurant`, `thai_restaurant`, `cafe`, or `bakery`.
- Do not retain contributor-only exact address or coordinates unless another existing product flow requires them. A display title, `data_id`, normalized type, and provider link are sufficient for reviewer context.

#### `reviews` additions

```text
google_review_id string nullable unique
reviewer_id UUID nullable foreign key -> reviewers.id
observed_data_id string nullable
seen_via_restaurant_at nullable
seen_via_contributor_at nullable
contributor_generation integer nullable
provider_date_text nullable
publication_date_lower_bound nullable
publication_date_upper_bound nullable
publication_date_precision: exact | day | week | month | year | unknown
publication_date_is_approximate boolean not null default false
publication_date_basis: published | edited_or_displayed | unknown
```

- Continue using the internal review UUID as the stable primary key. `google_review_id` is a unique external deduplication key, not the database primary key.
- Every accepted review maps to a canonical `place_id`. Contributor-only reviews map through `place_data_ids` to an observed place even when the official Google Place ID is not yet known.
- Retain the contributor-supplied Maps `data_id` as `observed_data_id` on the review when known, even after its canonical place gains an official Place ID. `place_data_ids` remains the authoritative many-reviews-to-one-place mapping.
- `reviewer_id` permits one stored public review to appear in both restaurant-centric and reviewer-centric views without duplicating its content.
- Keep `review_origins` for provider provenance and `review_images` for ordered image metadata. They are supporting tables, not duplicate review stores.
- The migration marks all existing places `selected`, backfills unambiguous canonical Google review IDs from existing origins before adding the unique constraint, and resolves any pre-existing duplicate canonical rows through the current deduplication rules rather than failing the constraint creation.

Required indexes include:

- Unique `reviewers.google_contributor_id`
- Unique `reviews.google_review_id` where non-null
- Unique `place_data_ids.data_id`
- An index on non-null `reviews.observed_data_id`
- `reviews(reviewer_id, contributor_generation, publication_timestamp)`
- Existing `reviews(place_id, publication_timestamp)`
- A supported index for joining/filtering place normalized type and comparison family

### Venue-type classification and storage allowlist

Use `hl=en`, normalize deterministically, and version the classifier as `food_drink_v1`. Do not use the LLM, place title, reviewer name, review text, address, or coordinates to guess whether a result is a restaurant.

Normalization must trim whitespace, case-fold, collapse repeated whitespace, normalize `Café` to `cafe`, and normalize `bar and grill`/`bar & grill` to the same canonical value.

Canonicalize accepted values and families as follows:

```text
restaurant or * restaurant -> restaurant or *_restaurant -> restaurant
diner                       -> diner                       -> restaurant
bistro                      -> bistro                      -> restaurant
cafeteria                   -> cafeteria                   -> restaurant
food court                  -> food_court                  -> restaurant
bar & grill                 -> bar_and_grill               -> restaurant
cafe                        -> cafe                        -> cafe
coffee shop                 -> coffee_shop                 -> cafe
bar                         -> bar                         -> bar_or_pub
pub                         -> pub                         -> bar_or_pub
brewery                     -> brewery                     -> brewery_or_winery
winery                      -> winery                      -> brewery_or_winery
bakery                      -> bakery                      -> bakery_or_dessert
dessert shop                -> dessert_shop                -> bakery_or_dessert
ice cream shop              -> ice_cream_shop              -> bakery_or_dessert
```

Accept only high-confidence `place_info.type` values matching one of these rules:

```text
exactly "restaurant"
any normalized type ending in " restaurant"
cafe
coffee shop
diner
bistro
cafeteria
food court
bar & grill
bar
pub
brewery
winery
bakery
dessert shop
ice cream shop
```

Examples accepted by the suffix rule include `Pizza restaurant`, `Thai restaurant`, `Buffet restaurant`, `Vegan restaurant`, and `Fast food restaurant`.

Do not accept unrelated or ambiguous types, including hotel, resort, lodge, supermarket, grocery store, convenience store, generic store, market, catering service, event venue, wedding venue, or a missing/localized/unknown type. `Patisserie` and other unlisted synonyms remain excluded until explicitly added to a later classifier version.

One exception is an exact incoming `google_review_id` match to an already stored review whose canonical place is independently classified as an accepted food-and-drink venue. In that case the existing trusted place classification establishes eligibility; do not delete or reject the canonical restaurant review because the contributor response's type is missing or broader.

For every rejected contributor result:

- Do not create a place, data-ID mapping, review, origin, or image row.
- Do not retain its review ID, text, rating, place title, address, coordinates, `data_id`, URL, images, or structured details.
- Retain only aggregate counters for returned, accepted, rejected non-food, rejected unknown/ambiguous type, rejected missing required data, and duplicate rows.
- Never persist the raw contributor response or log rejected payload contents.

### Contributor ingestion, deduplication, and atomicity

The live operation performs no open database transaction while waiting for SerpApi. After a successful response:

1. Validate that the requested contributor ID is still associated with the selected reviewer.
2. Parse top-level public contributor metadata and the complete returned list in memory.
3. Validate each candidate: non-empty `review_id`, integer rating from 1 through 5, `place_info.data_id`, and an allowlisted type or independently accepted existing place. Review text is optional.
4. Classify all candidates before persistence and calculate aggregate rejection counts without retaining rejected payloads.
5. Load all incoming Google review IDs in one indexed query. Never scan every unmatched/observed review row and never use fuzzy title/address matching.
6. Match canonical reviews first by exact `google_review_id`/provider review ID. An exact match updates/enriches the existing review, reviewer relationship, provenance, and seen timestamps.
7. Resolve the place through `place_data_ids`. If no mapping exists, create one supported `observed` place and its mapping. Do not make a Place Results request merely to calculate reviewer statistics.
8. If the current contributor review ID matches the restaurant review already open in the application, map that contributor `data_id` directly to the current canonical place. The validated sample proved this exact review-ID overlap is available.
9. If a later restaurant fetch proves through an exact review-ID overlap that an observed place and selected place are the same, merge them transactionally, rewrite foreign keys/data-ID mappings, and preserve one canonical review. Do not infer a merge solely from similar names or addresses.
10. Increment `reviewers.context_generation` once and stamp every accepted review observed in the successful snapshot with that generation.
11. Batch-upsert accepted places, mappings, reviews, origins, and image metadata in one short transaction. Commit the new reviewer generation, counters, and `context_fetched_at` only after the full accepted snapshot is durable.
12. Calculate and return the requested comparison from the accepted in-memory set or committed generation. The frontend must not wait for per-review API calls or an LLM.

When the same SerpApi review already has a `review_origins` row from restaurant ingestion, update that origin instead of creating a duplicate origin with the same provider/review ID. Do not overwrite a known official `provider_place_id` merely with a contributor `data_id`; retain the latter in `reviews.observed_data_id` and `place_data_ids`.

If parsing, persistence, cancellation, or provider work fails, do not advance the generation and do not partially replace a prior valid snapshot. Preserve and continue displaying the prior snapshot as stale, with the failed refresh operation separately visible.

The latest reviewer context is defined by `reviews.reviewer_id = reviewer.id` and `reviews.contributor_generation = reviewer.context_generation`. Older canonical reviews may remain for deduplication or restaurant display but do not affect the latest reviewer baseline unless they were observed in the latest successful contributor snapshot.

### Type normalization for comparison

Store type classification once on the canonical place rather than repeatedly classifying it during every stats request.

For a selected current restaurant, choose the exact normalized type using this priority:

1. An already stored SerpApi Maps/restaurant primary type when it is allowlisted and specific.
2. An official Google Places primary type when available.
3. Iterate Google `place_types` in provider-supplied order and choose the first supported specific `*_restaurant` value, skipping generic `restaurant`, `food`, `point_of_interest`, `establishment`, delivery, takeaway, and store types.
4. If there is no specific restaurant subtype, choose the first explicitly allowlisted non-restaurant food-and-drink type in provider order.
5. Use generic `restaurant` only when no more specific supported value exists.
6. Otherwise, report that an exact-type comparison is unavailable; do not guess from the restaurant name or review content.

Contributor history normally uses `place_info.type`, for example:

```text
"Pizza restaurant" -> normalized_venue_type=pizza_restaurant, comparison_family=restaurant
"Cafe"             -> normalized_venue_type=cafe,             comparison_family=cafe
"Bar"              -> normalized_venue_type=bar,              comparison_family=bar_or_pub
"Bakery"           -> normalized_venue_type=bakery,           comparison_family=bakery_or_dessert
```

Generic `Restaurant` remains `restaurant`. It must not be silently promoted to `pizza_restaurant` or another cuisine. A generic restaurant therefore does not enter an exact pizza comparison, although it may enter a separately labeled broader restaurant-family comparison.

### Comparison rules

The default top-of-profile comparison filters the latest accepted snapshot by:

```text
same reviewer
AND latest successful contributor generation
AND normalized_venue_type = current restaurant normalized_venue_type
AND canonical place_id != current restaurant place_id
AND valid rating from 1 through 5
AND date within the selected time window
```

Excluding the canonical current place, rather than only the current review row, prevents multiple reviews of the same restaurant from entering its own baseline.

Return deterministic statistics:

```text
sample_size
average_rating
median_rating
sample_variance       -- PostgreSQL var_samp semantics; null for fewer than 2 rows
standard_deviation    -- PostgreSQL stddev_samp semantics; null for fewer than 2 rows
difference_from_average = current_rating - average_rating
rating_distribution for exact ratings 1 through 5
```

The response also discloses `match_level`, normalized type/family, current rating, selected time window, latest snapshot fetch time/generation, provider results returned, accepted count, and whether any dates are approximate.

Sample-size presentation rules:

- `0`: `No public matching-category history observed`; no numerical baseline.
- `1–2`: show individual observed ratings and sample size; do not present variance or a conclusion.
- `3–4`: show average, median, and distribution with a visible `Small sample` label.
- `5+`: show the full deterministic statistics.
- `10+`: may use calmer wording such as `larger observed sample`, while still describing the result as observational.

Default to exact type. If exact-type `sample_size < 5`, the API may also calculate `comparison_family`, but the UI must label it separately, for example `Broader restaurant comparison`. Never silently mix exact and broader rows.

Use neutral wording such as:

```text
The reviewer rated this pizza restaurant 1.2 stars above their observed average for four other pizza restaurants.
```

Do not say that the current review is better, worse, more credible, more accurate, or more meaningful.

### Time-window rules

- Default to `two_years`; also support `six_months`, `one_year`, and `all_observed` without another provider request.
- Use an exact ISO publication timestamp when a restaurant-origin response supplies one.
- The tested contributor response supplied relative values such as `3 months ago`, `a year ago`, or `Edited a year ago` and no `iso_date`. Preserve the raw provider date text and derive bounded approximate dates relative to `context_fetched_at`.
- Apply conservative relative-date buckets: `six_months` includes day/week values and month values from one through five but excludes `6 months ago`; `one_year` includes day/week/month values through 11 months but excludes `a year ago`; `two_years` includes day/week/month values plus `a year ago` but excludes `2 years ago` and older. Singular forms such as `a day`, `a week`, and `a month` map to one. Apply the same bucket after stripping an `Edited ` prefix.
- Treat `Edited ...` as provider-displayed activity time, not a guaranteed original publication time. Set `publication_date_basis=edited_or_displayed` and disclose the approximation.
- Rows with an unknown/unparseable date are excluded from bounded windows and may appear only in `all_observed`.
- Time-window changes recalculate locally through indexed SQL and consume no Google, SerpApi, or LLM call.

### Response and presentation example

```json
{
  "reviewer": {
    "id": "uuid",
    "display_name": "Public name",
    "local_guide": true,
    "provider_review_count": 1031,
    "provider_photo_count": 341
  },
  "context": {
    "status": "available",
    "fetched_at": "2026-08-02T00:00:00Z",
    "provider_results_returned": 200,
    "accepted_food_and_drink_count": 63,
    "rejected_count": 137
  },
  "comparison": {
    "current_rating": 4,
    "match_level": "exact_type",
    "normalized_venue_type": "pizza_restaurant",
    "time_window": "two_years",
    "sample_size": 4,
    "average_rating": 4.0,
    "median_rating": 4.5,
    "sample_variance": 2.0,
    "standard_deviation": 1.4142,
    "difference_from_average": 0.0,
    "distribution": {"1": 0, "2": 1, "3": 0, "4": 1, "5": 2},
    "contains_approximate_dates": true
  }
}
```

The initial implementation was validated against a live contributor response associated with a stored pizza-restaurant review: 200 results were returned, 63 matched the food-and-drink allowlist, five had the exact `Pizza restaurant` type including the current place, and the four-place comparison was computed locally. This is a validation example, not a hardcoded fixture or product assumption.

### Performance and caching

- The live provider request is expected to dominate first-load latency. In the validation sample, SerpApi reported 2.8 seconds of processing, while local classification and statistics over 200 rows took approximately 0.01 seconds.
- Open the local reviewer profile immediately and keep it usable while history loads.
- Parse and classify the provider list in memory, batch-read incoming review IDs, and batch-upsert accepted data. Do not issue one database or provider request per returned review.
- Include the default comparison in the terminal provider-operation result so statistics appear as soon as the one fetch/persist operation finishes.
- Cache/persist the contributor snapshot by reviewer, not by current restaurant. All future restaurant/type/time comparisons derive from that shared snapshot.
- Never automatically refresh on profile open, application start, hover, restaurant sync, or stale-state detection.
- Contributor enrichment is a single provider request rather than a pagination loop. Cooperative cancellation is checked before the request and again before persistence. Cancellation during an in-flight request cannot guarantee the provider search was avoided; settle its outcome conservatively and do not advance the context generation when cancellation wins before commit.

Storage remains ordinary PostgreSQL row/URL storage: no raw response bodies and no downloaded image binaries. A conservative planning allowance is approximately 1–5 MB for a full 200-result normalized contributor response before allowlist reduction; the accepted-only policy will normally retain less. Even a deliberately conservative 10 MB per reviewer would use about 1 GB for 100 loaded reviewer contexts, well within the planned Oracle storage boundary.

### Retention, deletion, privacy, and attribution

- Retain only allowlisted food-and-drink contributor reviews in the canonical shared review model. Do not retain non-food contributor results.
- Contributor-only reviews may be removed when their reviewer context is deleted. A review also confirmed by restaurant ingestion remains as a canonical restaurant review.
- On context deletion, remove contributor-only places/reviews/origins/images that have no other canonical use, clear contributor generation/counters, and clear contributor-snapshot membership from restaurant-confirmed reviews without deleting those restaurant reviews.
- Require a UI confirmation before context deletion and return the counts of contributor-only reviews/places removed versus restaurant-confirmed reviews preserved.
- Do not send contributor profiles, metadata, histories, or comparisons to the LLM.
- Do not infer race, ethnicity, nationality, religion, gender, age, disability, politics, home location, travel patterns, or other sensitive/personal traits.
- Do not use reviewer labels, avatar content, exact addresses, coordinates, Local Guide status, contribution points, review count, photo count, text length, or travel history as a credibility score.
- Store only public metadata needed for the feature, expose a delete action, and show Google/SerpApi attribution plus direct source links for displayed public reviews.
- Direct provider-hosted avatars/images follow the same host allowlist, referrer policy, accessibility, and no-binary-storage rules as BL-009.
- Keep this feature disabled for a public release until provider terms, privacy, retention, deletion, and attribution behavior have been reviewed. The private family deployment remains the initial scope.

### Failure behavior

- Missing contributor ID: show only the available author information and source link; do not offer analysis.
- Missing profile totals on older stored rows: show `Not available`; do not fetch automatically.
- Budget exhausted or confirmation declined: leave the local profile usable and unchanged.
- Provider error or cancellation: keep any previous valid snapshot and show the operation failure separately.
- Malformed individual accepted candidate: accept the rest of the successful response, increment a rejection counter, and do not retain the malformed payload.
- Invalid top-level contributor response or failed database transaction: fail the operation atomically and preserve the previous generation.
- Zero supported results or zero exact-type matches: display unavailable evidence, never a zero-quality/credibility result.

### Implementation order

1. Add the reviewer, data-ID mapping, canonical review-ID, type-classification, relative-date, generation, and supporting indexes/migration.
2. Extend normal restaurant-review normalization/upsert and API schemas to capture reviewer metadata already present in paid restaurant responses.
3. Add and unit-test the deterministic versioned food-and-drink type classifier and relative-date parser.
4. Add local reviewer profile/comparison repositories and GET endpoints; prove they cannot call provider clients.
5. Add the contributor provider adapter, allowlist-before-persistence pipeline, batch deduplication/place mapping, generation transaction, and deletion service.
6. Integrate the POST with BL-007 reservation, idempotency, per-contributor locking, operation polling, settlement, and cancellation boundaries.
7. Add the desktop right-pane/mobile full-page reviewer route, Back behavior, local profile, confirmation, operation state, comparison header, time selector, broader fallback, and deletion/refresh actions.
8. Add backend, integration, frontend, and Playwright coverage before changing the backlog status to `Done`.

### Completion notes

- Added migration `0008_reviewer_context.py` with shared reviewers, contributor Maps data-ID mappings, contributor-observed canonical-review fields, venue classifications, reviewer operation references, and operation-type usage reporting.
- Added local-only reviewer profile/comparison/delete APIs, explicit feature gating, reusable snapshot `200` responses, and one-search asynchronous contributor operations using the shared SerpApi reservation budget.
- Added deterministic allowlisted venue classification, relative-date normalization, contributor snapshot generation replacement, contributor-only context deletion, and reversible contributor profile enrichment.
- Added reviewer links, local profile navigation, explicit analysis/refresh/delete controls, local time-window comparison selection, and production-disabled UI gating.
- Reviewer context is presented as a URL-backed in-place review-pane mode: `/restaurants/{place_id}` for reviews and `/restaurants/{place_id}?reviewer={reviewer_id}&review={review_id}` for a reviewer. The workspace/search pane and restaurant header remain mounted; browser Back, refresh, review controls, loaded pages, and review-list scroll state are preserved.
- Added classifier/date tests and reviewer-profile Playwright smoke coverage.
- Refined the reviewer surface into three aligned semantic cards for the original review, exact-type comparison, and broader-family comparison. Comparison responses now include stored review bodies, return every matching row from the bounded contributor snapshot, and let the client reveal more rows locally without another API or provider call.
- Moved exact-type and broader-family rating summaries into a full-width responsive overview below the reviewer identity, while leaving the lower comparison cards focused on the historical review rows.

### Corrective follow-up: exact-type empty state hides retained history

A live validation with a current `tibetan_restaurant` review exposed an end-to-end gap. The contributor operation completed successfully, returned 50 provider records, and retained 29 allowlisted food-and-drink reviews. The only Tibetan-restaurant row was the current place, which the comparison correctly excluded, so the exact-type sample was zero. The backend also calculated a non-empty broader `restaurant`-family comparison, but the frontend rendered only the exact result and made the successful fetch look empty.

The following corrective work was required and is now complete:

#### Exact and broader comparison presentation

- Keep exact normalized type as the default and never merge exact and family rows into one sample.
- When the exact sample is below five, visibly render the separately labeled `broader_comparison` returned by the profile response. An exact sample of zero must not suppress a non-empty broader result.
- Use specific empty-state text, for example `No other Tibetan restaurant reviews observed`, followed by a distinct section such as `Broader restaurant comparison · 15 other restaurants` when family evidence exists. Do not use one generic empty message for both datasets.
- The current place remains excluded by canonical `place_id` from both exact and broader comparisons. The current review may still appear in the profile header but never in either baseline sample.
- Show which current normalized type and family produced each result. Humanize provider identifiers for display (`tibetan_restaurant` -> `Tibetan restaurant`) without changing the stored/query value.
- Apply the existing sample thresholds independently to each result. Show count and individual ratings for samples of one or two; average, median, distribution, and `Small sample` for three or four; and the full statistics for five or more.
- Render the rating distribution and the progressively disclosed list of all matching relevant accepted reviews for the active comparison. The list remains context, not a credibility ranking.

#### Aligned comparison cards and stored review bodies

- Render the original restaurant review, exact-type comparison, and broader-family comparison as separate semantic cards with the same outer width, border treatment, left edge, and responsive padding. Do not indent either comparison section relative to the original review.
- Keep the reviewer identity/profile header outside the cards. When comparison data exists, place a full-width `Rating overview` on its own row directly below the avatar/profile so the summaries do not compete with profile metadata for horizontal space.
- Show both the exact-type and broader-family summaries in that overview. They sit side by side when space permits and stack at narrower breakpoints. An empty exact-type result remains visible with its zero-sample explanation rather than yielding all of the space to the broader result.
- Put the shared `Window` selector in the overview header. Each non-empty summary exposes its sample count, average, median, standard deviation, and five-bucket rating distribution according to the existing sample-size rules.
- Use a moderately wider reviewer content limit and tighter vertical spacing than the review-list default. When the exact sample is empty and the broader sample exists, give the compact exact status roughly one-third of the summary row and the broader result the remaining space; use equal columns when both contain evidence.
- On wide screens, place a summary's statistics and rating distribution side by side rather than in consecutive vertical blocks. At narrower widths they stack naturally.
- Use one card per semantic section, not a dashboard of nested cards. The lower exact and broader comparison cards show their scope/count and divider-separated review rows without repeating the statistics already visible in the top overview.
- The comparison response includes `text` and `original_text` with each relevant review in addition to its ID, place title, rating, provider date text, approximation flag, and source URL. These bodies come from the already persisted canonical review; rendering them must not fetch SerpApi or Google.
- Return every row that matches the selected reviewer, generation, current-place exclusion, match level, and time window. The contributor snapshot is already bounded to at most 200 provider records, so the backend must not apply an additional silent display cap such as ten rows.
- Initially render five matching reviews per comparison card. If more are present, show an explicit `Show all N reviews`/`Show fewer reviews` control and an honest `Showing X of Y` count. This expansion is client-local and creates no API, budget, provider, or LLM work.
- Show a readable body preview when text exists, with a per-row `Show full review`/`Show less` control for long bodies. Keep the rating, displayed/approximate date, and direct Google source link visible. Use `No written review` when both stored text fields are empty.
- The exact-type empty card remains compact. A non-empty broader card renders its stored review rows immediately below it; its statistics remain in the top overview.
- Cards stack in one column on every viewport, preserve the existing mobile reviewer mode, and must not introduce horizontal overflow.

#### Time-window and local-query behavior

- The frontend must not hardcode every comparison request to `match_level=exact_type` while ignoring the broader result.
- On initial load, use the profile response's default two-year exact and optional broader comparisons without issuing a provider request.
- When the time window changes, query exact type for the selected window and, when exact has fewer than five rows or the user has selected the broader view, query `comparison_family` with the same `current_review_id` and time window. These PostgreSQL requests may run in parallel.
- Include `match_level` and `time_window` in frontend query keys. Never display a two-year broader result beside an exact result from a newly selected six-month, one-year, or all-observed window.
- Preserve the previous complete comparison while replacement local queries load, or show a scoped loading state. Apply both results together only when their returned window/generation still matches the active reviewer route and selection.
- Exact/broader selection and time-window changes are free local operations: they must not create a provider operation, reserve budget, change provider usage, or contact the LLM.

#### Provider-operation and rejection diagnostics

- A completed contributor operation must disclose `provider_results_returned`, accepted/retained count, rejected non-food count, rejected unknown/ambiguous-type count, rejected missing-required-data count, duplicate count, and committed context generation in typed terminal metadata.
- `collected_unique_count` retains its existing meaning of newly created canonical reviews, not total provider results or total retained history. Contributor ingestion must pass the actual newly created count to operation settlement; a refresh may legitimately report zero new rows while still reporting a non-zero retained snapshot.
- Return the typed reviewer-context summary from the single-operation status response as specified. Keep the recent-operation Developer drawer compact, but show enough returned/retained/new counts that a successful context fetch cannot look like it collected nothing.
- Do not hardcode `rejected_non_food_count` to zero. The classifier must distinguish an explicitly recognized non-food exclusion from a missing, localized, ambiguous, or otherwise unknown type. Continue retaining no identifying data for either rejected category.
- Rejection/operation accounting must not alter the allowlist or require retaining the raw contributor response.

#### Regression fixture and expected behavior

Add a synthetic regression scenario with a current Tibetan restaurant, the current place's contributor copy, zero other Tibetan restaurants, and multiple other allowlisted restaurant-family reviews. It must prove:

- Provider completion is successful and the accepted snapshot is committed.
- Exact comparison is empty because the current canonical place is excluded.
- Broader comparison is non-empty and visibly labeled.
- Changing each time window updates exact and broader results from PostgreSQL only.
- Returned, accepted, rejected, duplicate, new, and updated counters remain internally consistent.
- The Developer drawer and reviewer pane do not describe a successful retained snapshot as zero results merely because the exact-type sample is empty.

#### Test-harness update — 2026-08-02

- Added a normal backend contract test proving the profile response returns `broader_comparison` when the exact sample is zero.
- Added React component and application-query tests for broader rendering and same-window exact/family requests.
- Added a Playwright browser scenario using the synthetic exact-zero/non-empty-broader fixture.
- All corrective frontend and Playwright cases are ordinary required regression tests; no expected-failure markers remain.
- The corrective implementation renders the exact and broader datasets independently, requests synchronized local exact/family comparisons after a time-window change, includes every matching stored review with progressively disclosed bodies, and exposes terminal operation diagnostics.

### Acceptance criteria

- Clicking a reviewer opens a history-backed local profile with zero Google, SerpApi, or LLM calls.
- Reviewer metadata already present in restaurant-review results is stored and shown without contributor enrichment.
- Contributor history is fetched only after the separate explicit analysis/refresh action, confirmation when required, and BL-007 reservation.
- Concurrent/retried actions for the same contributor create at most one upstream search and one committed generation.
- A stored snapshot is shared across all appearances of the same reviewer and remains viewable when stale; opening it never refreshes automatically.
- Only the defined food-and-drink types are stored from contributor results. Rejected reviews and places leave no identifiable/raw persistence.
- Exact review IDs deduplicate restaurant and contributor observations without scanning all unmatched rows or fuzzy-matching places.
- A contributor `data_id` can map to an existing selected place through exact review-ID overlap, and later confirmed place merges preserve one canonical review.
- Default statistics compare other canonical places with the exact same normalized venue type, latest contributor generation, and last-two-years window while excluding the current place.
- Generic `Restaurant` rows never enter a more specific exact-type comparison without independent type evidence.
- Time filters and exact/broader comparison changes use PostgreSQL only and disclose approximate relative dates.
- The completed live operation returns the comparison so the UI shows statistics immediately after the fetch completes.
- If the exact sample is below five, a separately labeled broader result for the same time window is visible; an exact zero never hides non-empty retained family history.
- The original, exact-type, and broader-family sections share one aligned card layout, and comparison rows expose their already stored review text with local show-all/full-text controls.
- Provider total, returned result count, retained count, comparison sample size, match level, time window, and date approximation are all disclosed separately.
- Missing or small history follows the defined presentation thresholds and is never treated as poor credibility.
- Reviewer context does not automatically change main review filtering, ordering, or visibility.
- Provider usage records `serpapi_contributor_reviews` separately while enforcing the shared SerpApi budget.
- Refresh failure preserves the last valid generation; context deletion removes contributor-only history without deleting restaurant-confirmed canonical reviews.
- The user can open the public Google Maps profile and delete locally retained context.

### Required tests

Backend/unit tests must cover:

- Restaurant-review user metadata normalization and reviewer upsert
- Every allowlisted type, suffix restaurant type, normalized synonym, explicit exclusion, unknown/localized type, and classifier version
- Proof that rejected rows create no place/review/origin/image/data-ID records
- Required-field validation and rejection counters
- Exact review-ID batch deduplication, current-place data-ID mapping, observed-place creation, and confirmed-place merge
- Generation commit, failed/cancelled refresh preservation, snapshot reuse, deletion, and shared restaurant-confirmed reviews
- Exact-type SQL aggregation, current-place exclusion, rating distribution, median, `var_samp`, `stddev_samp`, zero/small samples, and separately labeled family fallback
- Exact and relative date parsing, `Edited` basis, all four time windows, unknown dates, and boundary behavior
- GET endpoints making no provider/LLM calls
- BL-007 budget exhaustion, reservation/settlement, idempotent replay, same-contributor races, cancellation, and provider failures

Frontend/Playwright tests must cover:

- Reviewer link availability and preserved restaurant/search/scroll state
- Desktop right-pane and mobile full-screen navigation plus browser Back
- Local profile rendering without provider usage changing
- Not-loaded, loading, available, stale, failed, and missing-metadata states
- Cost disclosure/confirmation, pending operation restoration, completion, failure, and explicit refresh
- Immediate comparison rendering, sample-size wording, separate broader fallback, time selector, approximate-date disclosure, and no paid request when filters change
- Regression coverage for exact zero plus non-empty broader history, including synchronized time-window changes and no provider-usage change
- Stored review-body serialization, removal of the old ten-row response cap, aligned cards, initial five-row disclosure, local show-all/show-fewer behavior, and long-text expansion
- Contributor-operation returned/retained/new counters and separate non-food versus unknown rejection accounting
- Context deletion and public Google Maps profile fallback

## BL-003 — Search-to-reviews split workspace

- Status: `Done`
- Area: Frontend layout and interaction design
- Priority: High
- Detailed design: [Design document, Section 3.6](design_doc.md#36-search-to-reviews-workspace)

### Goal

Replace the current dashboard-style page with a focused search-to-detail flow similar to a modern maps or list-detail application.

The interface should begin as a full-screen restaurant search. After a successful search or direct restaurant selection, it should transition into an adaptive split workspace with search and results on the left and the selected restaurant's reviews on the right.

The visual rule is:

> Panes and flat lists establish navigation. Cards are reserved for distinct review content.

Avoid surrounding every control, result, metric, and pane with its own card. The application should feel like a focused research workspace rather than a dashboard composed of unrelated widgets.

### Layout states

#### Initial search

The first screen contains only the product identity, short explanation, Google Places autocomplete, and free-form search:

```text
┌──────────────────────────────────────────────────────────────┐
│ Real Reviews                                           ⚙    │
│                                                              │
│                  Find a restaurant                           │
│          [ Google Places autocomplete                    ]    │
│                              or                              │
│          [ Free-form restaurant search               ][Go]   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

- Use the full viewport rather than showing empty workspace panes.
- Center the search controls in a restrained surface with a comfortable maximum width.
- A single subtle search surface is acceptable, but it should not look like a dashboard card.
- Keep the developer action visually secondary.
- Search errors remain close to the relevant input and do not trigger a transition.

#### Search results workspace

A successful free-form search shifts the search experience into a bounded left pane. The right pane shows a quiet selection prompt:

```text
┌────────────── Search and results ──────────────┬──────── Reviews ─────────────┐
│ compact autocomplete and free-form search     │ Select a restaurant          │
│───────────────────────────────────────────────│                              │
│ Restaurant result                             │                              │
│───────────────────────────────────────────────│                              │
│ Selected restaurant ▌                         │                              │
│───────────────────────────────────────────────│                              │
│ Restaurant result                             │                              │
└───────────────────────────────────────────────┴──────────────────────────────┘
```

- Use approximately 360–420 px for the left pane on large screens.
- Render restaurant results as compact flat rows with separators, not floating cards.
- Indicate selection with a tinted row background, clear border, or slim accent rail.
- Preserve the query, result list, scroll position, and pagination while the user opens different restaurants.
- Let the left and right panes scroll independently on desktop.

#### Selected restaurant and reviews

After selection, the right pane becomes the primary reading surface:

```text
┌────────────── Search and results ──────────────┬────── Restaurant reviews ─────┐
│ search controls                               │ restaurant name and address   │
│ result rows                                   │ source · sync · refresh        │
│                                               │ filter toolbar                 │
│                                               │───────────────────────────────│
│                                               │ ┌ Review card ──────────────┐ │
│                                               │ │ author · rating · date     │ │
│                                               │ │ text, photos, details      │ │
│                                               │ └───────────────────────────┘ │
└───────────────────────────────────────────────┴───────────────────────────────┘
```

- Keep the restaurant header and filter toolbar flat and sticky when practical.
- Constrain very long review lines to a readable width inside the flexible right pane.
- Keep review cards visually subordinate to the pane: low elevation, subtle border, and consistent spacing.
- Switching restaurant results updates only the right pane.
- Provide an explicit `New search` action to return to the initial full-screen state.

### Card strategy

Use cards for:

- Individual reviews
- Review photo galleries contained within a review
- Structured review details when they need a visually distinct subsection

Do not use cards for:

- The left or right workspace pane
- The restaurant header
- The review filter toolbar
- Every search control
- Provider usage metrics
- Individual metadata labels

Restaurant search results should normally be flat selectable rows. If extra separation is needed, use a card-like hover/focus treatment without persistent shadows or large gaps.

Review cards should use:

- Approximately 12–16 px corner radius
- A low-contrast border
- Little or no shadow in dark mode
- Clear author/rating/date hierarchy
- Review text as the primary content
- An optional horizontal image gallery
- Structured details below the text
- Source and future reviewer-context actions at the bottom

### Developer drawer

Remove provider usage from the normal page layout.

- Add a small gear icon trigger with accessible label `Developer` in the application chrome.
- Open provider usage in a right-side overlay drawer without resizing the workspace.
- Fetch provider usage only when the drawer opens or the user explicitly refreshes it.
- Display usage as compact rows or a table rather than metric cards.
- Support close button, `Escape`, focus trapping, focus restoration, and dialog labeling.
- Use a full-width drawer or bottom sheet on narrow screens.
- Allow the developer trigger to be disabled in public production configuration.

### Responsive behavior

- Large screens: persistent list/detail panes.
- Medium screens: narrower list pane with flexible detail pane.
- Small screens: one pane at a time, with search/results followed by restaurant reviews.
- Mobile review view includes a clear `Back to results` action.
- Preserve query, results, selected restaurant, filters, and scroll state across pane changes.
- Respect reduced-motion preferences and avoid horizontal overflow.

### Suggested component boundaries

- `AppShell`
- `SearchLanding`
- `SearchPane`
- `SearchResultList`
- `RestaurantReviewPane`
- `ReviewFilters`
- `ReviewList`
- `DeveloperDrawer`
- `ProviderUsagePanel`

Use TanStack Query for server state. Keep layout mode, selection, and drawer state in explicit React state. Enable the reviews query only with a selected restaurant and the provider-usage query only while the developer drawer is open.

### Implementation sequence

1. Extract the current search, results, restaurant, filters, reviews, and usage markup into components without changing behavior.
2. Add explicit landing, search-results, and restaurant workspace states.
3. Implement the desktop split-pane shell and state transitions.
4. Move provider usage into the lazy developer drawer.
5. Add selected-row styling, independent scrolling, sticky right-pane regions, and review-card styling.
6. Add mobile one-pane navigation and state preservation.
7. Add focus management, reduced-motion behavior, and frontend tests.
8. Remove the old dashboard layout after the new flow passes its acceptance tests.

### Implementation update — 2026-07-29

Implemented the first split-workspace pass.

- Replaced the dashboard-style page with a focused landing search experience.
- Added adaptive workspace state for search/results and restaurant reviews.
- Moved search/results into a compact left pane on desktop.
- Added a quiet right-pane selection prompt before a restaurant is selected.
- Added selected-row styling and flat compact result rows with separators.
- Kept review content as the primary card-based UI.
- Added mobile pane switching with `Back to results` in the review pane.
- Preserved query, search results, selected restaurant, filters, and pagination in React state while switching results.
- Moved provider usage out of the main page into a lazy `Developer` drawer.
- Provider usage now fetches only when the developer drawer opens or is refreshed.
- Added `New search` action to return to the landing state.
- Verified frontend tests and production build after the layout rewrite.

Follow-up completion update — 2026-07-29:

- Extracted the large `App.tsx` implementation into focused components and a user-location hook:
  - `AppChrome`
  - `SearchLanding`
  - `SearchForm`
  - `SearchPane`
  - `SearchResultList`
  - `Workspace`
  - `RestaurantReviewPane`
  - `ReviewFilters`
  - `ReviewList`
  - `DeveloperDrawer`
  - `ProviderUsagePanel`
  - `useUserLocation`
- Added a dedicated `WorkspaceProps`/layout type module for shared component contracts.
- Added Testing Library, jsdom, a Vitest setup file, and `vitest.config.ts`.
- Added focused App tests for landing state, free-form transition, autocomplete transition, result switching, developer drawer lazy usage fetching, and mobile-style back navigation.
- Improved developer drawer keyboard handling with Tab/Shift+Tab focus trapping, Escape close, dialog labeling, close button focus, and focus restoration.
- Added reduced-motion CSS handling for transitions, animations, and smooth scrolling.
- Verified lint, tests, and frontend production build after the extraction.

UI polish close-out — 2026-07-29:

- Applied the warm ivory / soft white / ink navy / terracotta / muted map blue palette.
- Changed the `Developer` text trigger to an accessible gear icon.
- Made the `Real Reviews` wordmark a home action without a persistent focus box after click.
- Changed autocomplete location bias from 5 km to 5 miles and updated the visible status copy.
- Added selected-restaurant header metadata for rating, review count, and distance in miles when available.
- Added one explicit Text Search enrichment request after direct autocomplete selection to obtain matching rating/distance metadata by Place ID while keeping autocomplete Place Details Essentials-only.
- Verified frontend lint, tests, and production build after the polish pass.

### Acceptance criteria

- Initial load shows only the focused search experience and no provider-usage card.
- A successful free-form search transitions into the split workspace.
- Direct autocomplete restaurant selection opens the split workspace with restaurant details.
- Selecting another result updates the right pane without clearing the left pane.
- Restaurant results are rendered as compact rows rather than a grid of cards.
- Reviews are the primary card-based content.
- Provider usage is accessible only through the developer drawer and is queried lazily.
- Desktop panes scroll independently.
- Mobile navigation switches cleanly between results and reviews while preserving state.
- Search, selection, loading, empty, error, cached, sync, refresh, and filter states remain understandable.
- Keyboard, focus, dialog, and reduced-motion behavior meet the requirements in Design Section 3.6.
- Frontend tests cover the landing state, both transition paths, result switching, drawer behavior, lazy usage fetching, and mobile back navigation.

## BL-004 — Exact-star filtering and deterministic review sorting

- Status: `Done`
- Area: Stored review API, PostgreSQL querying, and review controls
- Priority: High
- Detailed design: [Design Section 3.4](design_doc.md#34-review-filtering) and [Design Section 5.6](design_doc.md#56-stored-review-filtering-and-sorting)

### Goal

Let users filter a selected restaurant's stored reviews by one exact star rating and sort the result deterministically without calling Google, SerpApi, or the local LLM.

The feature extends the existing stored-review endpoint rather than adding a separate list endpoint:

```http
GET /api/v1/restaurants/{place_id}/reviews?rating=4&sort=rating_high
```

### Backend and API plan

- Accept an optional `rating` query parameter constrained to the integers 1 through 5.
- Rating is equality-only: selecting 4 stars means `Review.rating == 4`, never 4 stars and above.
- Accept a `sort` enum with `recent`, `oldest`, `rating_high`, and `rating_low`.
- Default to no rating filter and `recent` sorting.
- Map the allowlisted sort enum to SQLAlchemy ordering-expression tuples in the repository.
- Never accept arbitrary client-controlled column names, directions, SQL fragments, or order expressions.
- Use publication timestamp for recent/oldest ordering.
- Put null ratings and timestamps last.
- Add deterministic tie-breakers, ending with review ID.
- Return `total` for all stored reviews and `filtered_total` for the exact-rating result.
- Continue returning the restaurant's saved topics independently of review filtering and ordering.
- Keep filtering and sorting ahead of future limit/cursor pagination.

The intended ordering definitions are:

- `recent`: publication timestamp descending, then ID ascending
- `oldest`: publication timestamp ascending, then ID ascending
- `rating_high`: rating descending, publication timestamp descending, then ID ascending
- `rating_low`: rating ascending, publication timestamp descending, then ID ascending

Review synchronization and refresh responses remain unfiltered. After either operation, the frontend invalidates and refetches the parameterized stored-review query so the active deterministic controls are applied by PostgreSQL.

### Frontend plan

- Show the controls only after at least one review exists.
- Add a rating selector with `Any rating`, `5 stars`, `4 stars`, `3 stars`, `2 stars`, and `1 star`.
- Add a sort selector with `Most recent`, `Oldest`, `Highest rated`, and `Lowest rated`.
- Apply control changes immediately without an Apply button or debounce.
- Include place ID, exact rating, and sort in the React Query cache key.
- Display `filtered_total of total reviews`.
- Provide a reset action that restores any rating and most recent sorting.
- Show a useful empty state when an exact rating has no matches.
- Clear active LLM-selected IDs when the exact-rating filter changes because the candidate set changed.
- Preserve active LLM-selected IDs when only the sort changes because membership is unchanged.
- Clear restaurant-specific rating and semantic state and restore most-recent sorting when another restaurant is selected.

### Relationship to semantic filtering

PostgreSQL performs exact-rating filtering and deterministic sorting without the LLM. When a semantic filter is active, the unified backend pipeline in `BL-005` applies these deterministic controls before LLM inference and returns the complete, sorted review objects. The frontend does not resend stored reviews or perform the final selected-ID intersection.

### Non-goals

- Minimum-rating behavior such as 4 stars and above
- LLM-generated SQL or executable filter code
- Arbitrary field or direction sorting
- Provider relevance sorting within BL-004; it is now separately designed in [`BL-011`](#bl-011--google-relevance-first-review-ingestion-and-local-sorting)
- Date-range filtering
- Stored-review pagination as part of this item

### Implementation update — 2026-07-30

Implemented the deterministic stored-review controls.

- Added validated `rating` and `sort` query parameters to `GET /api/v1/restaurants/{place_id}/reviews`.
- Added `ReviewSort` allowlist values: `recent`, `oldest`, `rating_high`, and `rating_low`.
- Mapped sort values to SQLAlchemy ordering expressions with null-last behavior and review-ID tie breakers.
- Added repository exact-rating filtering and total/filtered count queries.
- Added `filtered_total` to stored-review list responses.
- Kept topics place-level and independent from filtering/sorting.
- Updated frontend review query keys to include place ID, exact rating, and sort.
- Replaced minimum-rating behavior with exact-star options.
- Added deterministic sort selector and reset action.
- Displayed `filtered_total of total reviews` and useful empty states.
- Rating changes clear active semantic selections; sort changes preserve them.
- Restaurant changes reset rating, sort, and semantic state.
- Added backend sort allowlist/tie-breaker tests and frontend control/cache-key tests.
- Verified backend lint/tests, frontend lint/tests, and frontend production build.

### Acceptance criteria

- Each rating option returns only reviews with that exact rating.
- `Any rating` includes rated and unrated reviews.
- Reviews with missing ratings are excluded whenever an exact rating is selected.
- All four sort modes use the documented null-last, stable ordering.
- Invalid ratings and unknown sort values are rejected by API validation.
- The API reports correct `total` and `filtered_total` values.
- Basic filtering and sorting make no Google, SerpApi, or LLM requests.
- Topics remain unchanged when the review list is filtered or sorted.
- Rating changes clear stale semantic selections; sort-only changes preserve them.
- Tests cover repository queries, route validation, counts, null handling, stable ties, frontend controls, cache keys, reset behavior, and interaction with semantic filtering.

## BL-005 — Unified backend semantic filtering and reviewer-label dropdown

- Status: `Done`
- Area: Local LLM filtering, stored review API, and review controls
- Priority: High
- Detailed design: [Design Section 3.4](design_doc.md#34-review-filtering), [Design Section 5.7](design_doc.md#57-unified-backend-semantic-filtering), and [Design Section 8](design_doc.md#8-backend-api)

### Goal

Move the complete semantic-filtering pipeline into FastAPI and add an always-visible reviewer-label dropdown that uses the local LLM for explicit label-equivalence decisions.

The dropdown initially contains:

- `Any reviewer label`
- `Chinese`
- `Korean`
- `Japanese`

`Any reviewer label` is the default and performs no label-related LLM inference.

### Backend-owned options

Define the initial name choices once in the backend:

```python
REVIEWER_LABEL_OPTIONS = {
    "chinese": "Chinese",
    "korean": "Korean",
    "Japanese": "Japanese",
}
```

- Add `GET /api/v1/reviews/filter-options` to return the value/label pairs.
- Render the frontend dropdown from that response rather than duplicating the hardcoded list in TypeScript.
- Validate every submitted label key against the backend mapping.
- Adding another name later requires adding one backend mapping entry.

### Unified filter API

Replace the current top-level semantic-filter contract with:

```http
POST /api/v1/restaurants/{place_id}/reviews/filter
```

Example:

```json
{
  "rating": 4,
  "reviewer_label": "chinese",
  "content_filter": "mentions outdoor seating",
  "sort": "recent"
}
```

The fields are independent:

- Exact rating and sort use the deterministic controls in `BL-004`.
- Reviewer label is null or a race, currently one of `chinese`, `korean`, `japanese`, `american`, and `italian`.
- Content filter is an optional bounded natural-language query.
- Name-only, content-only, combined, and deterministic-only requests must all behave consistently.

### Filtering pipeline

1. Load the selected restaurant and stored reviews from PostgreSQL.
2. Apply the optional exact-rating SQL filter.
3. For an active reviewer label, send only canonical review IDs and non-empty author display names to the isolated label-equivalence prompt.
4. For an active content query, send only canonical review IDs, review text, rating, and publication date to the isolated content prompt.
5. Parse each response with a strict Pydantic schema containing `selected_review_ids: list[UUID]`.
6. Validate returned IDs against the specific candidate batch that produced them.
7. Deduplicate valid IDs and intersect the label/content sets when both filters are active.
8. Fetch matching reviews using parameterized SQLAlchemy `Review.id.in_(selected_ids)` constrained by the selected place.
9. Apply the allowlisted SQL sort.
10. Return complete review objects and counts to the frontend.

The frontend renders the backend response and does not perform the final selected-ID intersection.

### Reviewer-label LLM input

The label prompt receives only:

- Selected target name
- Canonical review ID
- Stored author display name

It never receives review text, rating, date, profile history, location, avatar, or restaurant metadata. Blank names are skipped and counted. Batch by model tokens and a maximum candidate-name count without splitting an individual display name.

The task is explicit name equivalence only. It must not infer or classify gender, race, ethnicity, nationality, religion, age, or another personal trait. Treat display names as untrusted data, ignore instructions embedded in them, and exclude uncertain entries.

### Frontend behavior

- Keep the reviewer-label dropdown visible beside rating and sort whenever reviews exist.
- Keep the natural-language content filter independently available below the deterministic controls.
- Selecting a named option runs the unified backend filter; selecting `Any reviewer label` removes the label constraint without a label LLM call.
- Topic chips update the content query without changing the selected reviewer-label option.
- Changing rating or reviewer label invalidates affected semantic results.
- Changing sort alone can reuse selected IDs.
- Refreshing or synchronizing reviews invalidates cached semantic results.
- Reset restores any rating, any reviewer label, an empty content query, and most-recent sorting.

### Caching and failure behavior

- Do not persist LLM decisions as durable reviewer classifications.
- If neither semantic filter is active, use the deterministic stored-review endpoint and skip the LLM.
- Invalid JSON, unknown IDs, or one failed batch fail the semantic operation.
- On failure, keep the deterministic SQL result visible and offer retry.
- An empty selected-ID set returns an empty result without constructing an empty SQL `IN` clause.

### Non-goals

- Free-text reviewer-label targets
- SQL, trigram, edit-distance, or fuzzy-string name matching
- LLM-generated SQL
- Demographic or sensitive-trait inference
- Durable storage of label-equivalence classifications
- Provider calls during filtering

### Implementation update — 2026-07-30

Implemented the unified backend semantic-filtering pass.

- Removed the old top-level `POST /api/v1/reviews/filter` route and frontend client call.
- Added `GET /api/v1/reviews/filter-options` with backend-owned Chinese/Korean/Japanese reviewer-label options.
- Added `POST /api/v1/restaurants/{place_id}/reviews/filter` for unified deterministic, reviewer-label, and content filtering.
- Added validated backend request schema for exact rating, reviewer-label key, content filter, and allowlisted sort.
- Reused deterministic exact-rating SQL filtering and allowlisted sorting from `BL-004`.
- Added isolated reviewer-label LLM batching that sends only target label, canonical review ID, and stored author display name.
- Added isolated content LLM batching that sends only review ID, text, rating, and publication date.
- Added strict JSON/Pydantic response parsing, one controlled JSON retry, per-batch UUID validation, deduplication, and label/content intersection.
- Added SQLAlchemy ID-constrained review loading that remains scoped to the selected place and skips empty `IN` queries.
- Added full filter responses with complete review objects, total/candidate/filtered counts, selected IDs, skipped missing-name count, applied controls, topics, and `llm_used`.
- Updated the frontend to render backend filter responses directly without performing final selected-ID intersection.
- Added reviewer-label dropdown populated from the backend options endpoint.
- Kept topic-chip shortcut behavior: clicking a topic populates the content field and immediately submits the unified filter with current rating/name/sort.
- Added inline semantic-filter failure messaging that preserves previous/deterministic review results.
- Deferred reviewer-label caching to a future optimization requiring a formal `review_corpus_version` and shared/bounded cache.
- Verified Compose config, backend lint/tests, frontend lint/tests, and frontend production build.

### Follow-up optimization: reviewer-label filter caching

Reviewer-label result caching is intentionally deferred. A future implementation should add a formal `review_corpus_version` on the restaurant/place, increment it when reviews materially change or are deleted, and cache label-filter results in a bounded TTL/LRU or shared cache keyed by place, corpus version, rating, and reviewer-label key.

### Acceptance criteria

- The dropdown always offers Any, Chinese, Korean, and Japanese after reviews exist.
- The dropdown options come from the backend filter-options endpoint.
- Any reviewer label produces no label-related LLM request.
- Name-only payloads contain no review content or unrelated author/profile data.
- Content-only payloads contain no reviewer label.
- Combined label/content filtering intersects validated backend ID sets.
- Every model-returned value is a valid UUID from its specific batch.
- PostgreSQL ID filtering uses bound SQLAlchemy parameters and remains constrained to the selected place.
- The backend returns complete, correctly sorted review objects and accurate total/candidate/filtered/skipped counts.
- The frontend performs no final review-ID filtering.
- Rating/name changes, sort-only changes, refreshes, resets, empty results, and failures follow the documented state rules.
- Unit, integration, contract, and frontend tests cover every supported filter combination and invalid-response path.

## BL-006 — Mobile-first responsive web app and Home Screen experience

- Status: `Done`
- Area: Frontend responsive layout, navigation, and installable web experience
- Priority: High
- Detailed design: [Design document, Section 3.6.5](design_doc.md#365-responsive-behavior)

### Goal

Make the existing React application comfortable and app-like on family members' iPhones while retaining one shared frontend for desktop browsers, mobile browsers, and the installed Home Screen experience.

This feature does not create a second mobile application or duplicate the landing/search screen. It refines shared components and presentation around the existing search-to-reviews workflow.

### Current foundation

The current frontend already:

- Uses a full-screen landing search.
- Uses a persistent list/detail split at the `lg` breakpoint.
- Shows one surface at a time below that breakpoint.
- Tracks a mobile results/reviews pane and provides a `Back to results` action.
- Uses responsive padding, wrapping review metadata, and a mobile developer bottom sheet.

The remaining work is targeted refinement rather than a frontend rewrite.

### Responsive layout

- Keep the desktop split workspace at 1024 px and wider.
- Below 1024 px, show landing search, search results, or restaurant reviews as one primary surface.
- Permit a tablet-landscape split only if both panes meet their minimum usable widths.
- Continue sharing search, restaurant, filter, and review components across all breakpoints.
- Do not introduce separately maintained desktop and mobile pages.

Expected mobile flow:

```text
Landing search
      ↓ search
Search results
      ↓ select restaurant
Restaurant reviews
      ↓ Back
Search results
```

A direct autocomplete selection returns to landing rather than an empty results list.

### Mobile navigation and state

- Synchronize restaurant selection with browser history through `pushState`/`popstate` or an equivalent client-side routing layer.
- Make the iOS back gesture and browser Back action return to the correct previous surface.
- Preserve the search query, results, pagination, selected restaurant, active filters, and per-surface scroll position across pane changes.
- Keep TanStack Query as the owner of server data; navigation history must not duplicate restaurant or review response data.
- Retain an explicit `New search` action that clears the workflow and returns to landing.

### Viewport, safe areas, and scrolling

- Replace exclusive dependence on `100vh` with `dvh` plus a compatible fallback.
- Account for mobile browser chrome, standalone Home Screen mode, rotation, the status area, and the bottom Home indicator.
- Use `viewport-fit=cover` only with explicit safe-area padding.
- Give fixed and sticky application chrome, drawers, and bottom sheets safe-area-aware padding.
- Establish one primary vertical scroller per mobile surface.
- Add the required `min-height: 0` and overscroll behavior to nested desktop panes.
- Prevent document-level horizontal overflow, including for long names, addresses, review text, and URLs.

### Restaurant header, topics, and filters

The current restaurant metadata and complete filter region must not remain one tall sticky block on phones.

Mobile restaurant reviews use:

```text
┌──────────────────────────────────┐
│ ← Results   Restaurant    Filters│  compact sticky navigation
├──────────────────────────────────┤
│ restaurant metadata and actions │
│ review topics → horizontal row   │
│                                  │
│ review cards                     │
└──────────────────────────────────┘
```

- Keep only Back, a truncated restaurant name, and Filters in the compact sticky mobile bar.
- Place full restaurant metadata and sync/refresh actions in normal scrolling content.
- Open filter controls in a safe-area-aware full-width bottom sheet or equivalent compact disclosure surface.
- Indicate when filters are active while the filter surface is closed.
- Use one filter column on phones, two columns on medium widths, and a horizontal toolbar only on sufficiently wide desktop review panes.
- Display topic chips in a horizontally scrollable, non-sticky row on phones and allow wrapping on wider layouts.
- Topic selection continues to populate and submit the existing content filter without an upstream provider request.

### Touch and accessibility behavior

- Give primary mobile actions approximately 44 by 44 CSS-pixel touch targets.
- Include application chrome, Back, Filters, fetch/sync, refresh, topic chips, Filter, Reset, and drawer controls.
- Keep focus handling, dialog labeling, focus trapping, Escape behavior, and focus restoration for the developer and filter sheets.
- Respect `prefers-reduced-motion`.
- Ensure controls remain understandable and correctly ordered for screen readers when desktop panes collapse into mobile surfaces.

### Home Screen installation

Add installable web-app metadata without introducing a second frontend:

- Web-app manifest
- Application name and short name
- Standalone display mode
- Stable start URL
- Theme and background colors matching the current palette
- Required application icons and Apple touch icon
- Document theme metadata

An initial service worker may cache versioned application-shell assets only. It must not cache API, restaurant, review, LLM-filter, Google, or SerpApi responses without a separate freshness and invalidation design.

### Suggested component changes

- Keep `SearchLanding`, `SearchPane`, `SearchResultList`, `RestaurantReviewPane`, `ReviewFilters`, and `ReviewList` shared.
- Extract a compact `MobileRestaurantBar`.
- Extract a `MobileFilterSheet` that renders the shared filter controls.
- Split the broad `WorkspaceProps` contract into search-pane and review-pane props as needed so responsive layout components do not receive unrelated state.
- Keep mobile presentation decisions outside provider and backend API modules.

### Testing plan

Add browser-level responsive tests because jsdom component tests do not apply Tailwind breakpoints or validate rendered geometry:

- 390×844 phone portrait
- 844×390 phone landscape
- 768×1024 tablet portrait
- 1280×800 desktop

Tests cover:

- Landing, results, and restaurant surfaces without horizontal overflow.
- Search-result selection and Back/popstate navigation.
- Direct autocomplete Back behavior.
- Preservation of query, results, filters, and scroll position.
- Compact sticky restaurant navigation.
- Filter bottom-sheet open, close, focus, and safe-area behavior.
- Topic-chip horizontal overflow and activation.
- Dynamic viewport-height behavior and standalone display mode.
- Developer bottom-sheet sizing.
- Touch-target sizing for primary actions.
- Reduced-motion behavior.
- Manifest metadata and application-shell caching boundaries.

### Non-goals

- Native Swift, Flutter, React Native, Capacitor, TestFlight, or App Store distribution.
- A separate mobile API or mobile-only copy of frontend business logic.
- Full offline restaurant search, review synchronization, or LLM filtering.
- Caching provider or API responses in the service worker.
- Redesigning the desktop visual palette or replacing the existing search-to-reviews model.

### Implementation sequence

1. Add responsive browser tests and document current mobile geometry.
2. Introduce dynamic viewport sizing, safe-area primitives, and mobile scroll ownership.
3. Add browser-history-aware results/review navigation and correct direct-selection Back behavior.
4. Extract the compact mobile restaurant bar and separate sticky navigation from scrolling metadata.
5. Add the mobile filter sheet, responsive filter grid, active-filter indication, and horizontal topic row.
6. Normalize primary mobile touch targets and long-content wrapping.
7. Add manifest, icons, standalone metadata, and the application-shell cache policy.
8. Verify portrait phone, landscape phone, tablet, desktop, reduced-motion, keyboard, and screen-reader behavior.

### Completion notes

- Added Playwright as a frontend dev dependency with a Docker Compose `e2e` profile/service using the Playwright browser image so production frontend images do not include browser dependencies.
- Added Chromium responsive coverage for 390×844, 844×390, 768×1024, and 1280×800, plus a WebKit mobile smoke test.
- Added dynamic viewport and safe-area primitives, mobile scroll ownership, horizontal-overflow protections, and touch-target normalization.
- Added history-backed mobile result/review navigation and direct-selection back behavior through shared React state and browser history.
- Added compact mobile restaurant navigation, bottom-sheet filters, non-sticky horizontally scrollable mobile topic chips, and desktop inline filters.
- Added Home Screen manifest metadata, theme metadata, SVG manifest icon, and Apple touch icon without adding a service worker.

### Acceptance criteria

- The desktop browser, mobile browser, and installed Home Screen experience use one React implementation.
- No separately maintained mobile landing or home page exists.
- Phone and tablet layouts present one usable primary surface without horizontal document overflow.
- Desktop retains the persistent list/detail workspace.
- The iOS/browser Back action returns from restaurant reviews to preserved search results.
- Direct autocomplete selection returns to landing rather than an empty results pane.
- Search, result, pagination, filter, selection, and scroll state survive mobile navigation.
- The mobile sticky region contains only compact navigation and does not hide most of the review viewport.
- Filter controls remain discoverable and usable in a safe-area-aware mobile disclosure surface.
- Filter controls use appropriate phone, medium, and desktop layouts.
- Topic chips scroll horizontally on phones and remain non-sticky.
- Primary actions provide the documented touch-target intent.
- Dynamic viewport sizing and safe-area padding work in browser and standalone modes.
- Home Screen installation shows the correct name, icon, theme, and standalone start route.
- The service worker, if added, caches only versioned application-shell assets.
- Responsive browser tests pass at all documented viewports and cover history, overflow, filters, reduced motion, and accessibility.

## BL-007 — Cost and concurrency protection

- Status: `Done`
- Area: Provider budgets, synchronization safety, and duplicate-request protection
- Priority: High
- Detailed design: [Design document, Section 18](design_doc.md#18-planned-feature-cost-and-concurrency-protection)

### Goal

Prevent simultaneous users, browser retries, or requests for different restaurants from exceeding the configured SerpApi allowance or starting duplicate paid work.

The existing per-place PostgreSQL advisory lock remains useful, but it protects only overlapping synchronization for the same restaurant. This item adds global, cross-request accounting and idempotency.

### Required behavior

- Reserve estimated SerpApi searches atomically before starting a synchronization, refresh, load-more operation, or reviewer-context lookup.
- Reject work before the first provider request when the remaining unreserved allowance is insufficient.
- Settle each reservation with actual successful/cached/failed counts and release unused capacity when the operation ends.
- Keep the configured plan-period budget and optional hourly safety ceiling authoritative in the backend.
- Continue using the per-place advisory lock so only one review mutation runs for a restaurant at a time.
- Accept an idempotency key for paid mutations and return the existing operation/result when the same key is retried.
- Apply a small configurable SerpApi concurrency limit.
- Keep `LLM_MAX_CONCURRENCY` separate from provider-search concurrency.
- Disable repeat frontend submission while an operation is pending and show the operation outcome beside the restaurant controls.

### Persistence and deployment boundary

- Budget reservation must be PostgreSQL-backed and transactional; an in-memory counter is not sufficient.
- Store provider, plan period, operation type, restaurant when applicable, requested units, settled units, status, idempotency key, and expiration/heartbeat timestamps.
- Expired abandoned reservations may be reclaimed only through a documented lease rule.
- A process-local semaphore is acceptable for the initial single-API-replica deployment, but production must remain at one API replica until concurrency control is shared across replicas.
- Never hold a database transaction open while waiting on Google, SerpApi, or the LLM.

### Failure and user experience

- Return stable error codes for budget exhausted, hourly ceiling reached, duplicate operation running, and idempotency conflict.
- Cost confirmation remains distinct from budget reservation: confirmation obtains user intent; reservation proves capacity.
- The UI should show estimated searches before confirmation and actual searches after completion.
- A failed request before provider contact consumes no settled search units.
- Uncertain provider outcomes are recorded conservatively and surfaced in the developer drawer.

### Non-goals

- Buying or automatically upgrading a SerpApi plan
- Distributed Redis infrastructure for the initial family deployment
- Parallel review synchronization for the same restaurant
- Treating locally tracked usage as the provider's billing system of record

### Completion notes

- Added PostgreSQL-backed provider budget-period and provider-operation/reservation records in migration `0005_provider_budget_ops.py` (the descriptive revision ID was shortened to fit the existing 32-character Alembic version column).
- Added transactional global reservation, lease expiry reclamation, idempotency fingerprints, same-place collision detection, settlement, release accounting, and conservative uncertain-request accounting.
- Added a 60-second process-local allowlisted SerpApi Account API snapshot cache. Only renewal date, remaining searches, hourly usage, and hourly limit are parsed; raw responses are never persisted or logged.
- Added configurable SerpApi request concurrency, reservation lease, and optional hourly safety ceiling.
- Added asynchronous in-process paid-operation execution, operation status/list/cancel endpoints, `202` replay headers, and cooperative cancellation at provider-page boundaries.
- Added frontend idempotency retention, operation polling, cancellation feedback, stored-review invalidation, and a recent-operation panel in the Developer drawer.

### Acceptance criteria

- Two simultaneous operations cannot reserve the same last unit of budget.
- Requests for different restaurants respect the same global allowance.
- Duplicate retries with the same idempotency key do not create another paid operation.
- Same-place concurrent mutations produce at most one active sync.
- Reservation settlement records successful, cached, failed, and released units.
- Crashed-operation reservations expire safely without silently double-spending.
- Tests cover atomic reservation races, same-place locking, different-place budget contention, idempotent retry, expiration, and settlement.

## BL-008 — Review pagination and load more

- Status: `Done`
- Area: Stored-review response sizing and explicit review collection
- Priority: High
- Detailed design: [Design document, Section 19](design_doc.md#19-planned-feature-review-pagination-and-load-more)

### Goal

Let users browse stored reviews incrementally and explicitly fetch older reviews without loading every stored review into the browser or confusing free database paging with paid SerpApi collection.

### Two distinct actions

1. `Show more saved reviews` reads the next page from PostgreSQL. It is local and does not consume provider usage.
2. `Fetch older reviews` resumes SerpApi collection for the restaurant. It may consume searches and requires an estimate, confirmation, and a BL-007 reservation.

These labels and cost treatments must remain visibly different.

### Stored-review pagination

- Extend `GET /api/v1/restaurants/{place_id}/reviews` with an allowlisted `page_size` and opaque `cursor`.
- Default to 20 reviews and cap a page at 50.
- Apply selected exact-rating filtering and deterministic sorting before keyset pagination.
- Preserve the existing stable review-ID tie breaker in every sort.
- Return `items`, `page_size`, `next_cursor`, `has_more`, `total`, `filtered_total`, topics, and topic fetch metadata.
- Reject cursors whose place, rating, sort, or version no longer matches the request.
- Reset accumulated pages when restaurant, rating, or sort changes.
- Keep topic data place-level and return it independently from the current review page.

### Upstream load more

The bullets below describe the implemented BL-008 newest-first behavior. [`BL-011`](#bl-011--google-relevance-first-review-ingestion-and-local-sorting) intentionally supersedes the provider-sort and recovery portions when relevance-first ingestion is implemented; free saved-review pagination remains unchanged.

- Add an explicit restaurant-scoped load-more operation rather than overloading the local `Show more` action.
- Resume from the latest valid stored provider cursor and request only the user-approved additional target.
- Do not apply the known-unchanged refresh shortcut; load more intentionally walks toward older reviews.
- If the provider cursor expired, offer a confirmed restart using the sort bound to that collection state and deduplicate all observed reviews. The current implementation binds to newest-first; BL-011 adds separate `qualityScore` and `newestFirst` states.
- Persist every completed page and updated cursor before requesting the next page.
- Return new-review count, total stored count, request count, stop reason, and the next resumable state.
- Never prefetch an upstream page automatically when the user scrolls.

### Semantic-filter boundary

- Initial BL-008 delivery paginates deterministic stored-review browsing.
- Existing semantic filtering remains bounded to the configured candidate maximum and returns its current complete result set.
- Do not rerun the LLM independently for each visible page.
- If semantic result sets later exceed that bound, add a versioned filter-result session or cache before paginating them.

### Completion notes

- Added migration `0006_review_pagination` with `review_corpus_version`, provider collection cursor state, and operation result metadata.
- Added opaque signed keyset cursors bound to place, exact rating, sort, and corpus version.
- Added saved-review pagination to `GET /api/v1/restaurants/{place_id}/reviews` with `page_size`, `cursor`, `next_cursor`, `has_more`, and corpus version fields.
- Added separate advisory `GET /reviews/load-more/options` and async paid `POST /reviews/load-more` using BL-007 reservation/idempotency/cancellation behavior.
- Added persisted provider cursor updates after each completed provider page, cursor-expiry recovery metadata, and restart-from-newest UI.
- Added frontend infinite saved-review paging with a distinct free `Show more saved reviews` action and separate paid `Fetch older reviews` choices.
- Added backend cursor, pagination contract, fixed-estimate, and load-more lifecycle tests plus Playwright saved-page append coverage.

### Acceptance criteria

- Opening a restaurant loads at most the configured first page of stored reviews.
- `Show more saved reviews` performs no Google, SerpApi, or LLM call.
- No stored review is skipped or repeated while paging a stable sort.
- Rating/sort/restaurant changes invalidate the old cursor and accumulated pages.
- `Fetch older reviews` clearly displays estimated and actual provider searches.
- Concurrent or retried load-more operations use BL-007 protections.
- Expired provider cursors recover without creating duplicate canonical reviews.
- Mobile and desktop retain scroll position while appending saved reviews.
- Backend and browser tests cover all supported sorts, ties, invalid cursors, empty final pages, provider-cursor recovery, and cost confirmation.

## BL-009 — Rich review data

- Status: `Done`
- Area: SerpApi review ingestion, persistence, API schemas, and review cards
- Priority: High
- Detailed design: [Design document, Section 20](design_doc.md#20-planned-feature-rich-review-data)

### Goal

Preserve and display the richer information Google attaches to individual reviews, including review photos and structured fields such as order type, meal type, price per person, sub-ratings, recommended dishes, dietary details, parking, and accessibility notes.

### Provider ingestion

- Read SerpApi `images`, `details`, and `translated_details` from each review.
- Preserve the raw dynamic label/value maps without assuming every restaurant uses the same keys.
- Accept only a top-level details object whose values are strings, finite numbers, booleans, or flat lists of those scalar types; omit `null` values and reject nested maps or nested lists.
- Normalize keys with Unicode NFKC normalization, trimming, lowercasing, spaces/hyphens converted to underscores, and repeated underscores collapsed. Preserve the original maps and do not split comma-separated strings into lists.
- Normalize only recognized display keys while retaining unknown valid fields for generic rendering.
- Preserve image order and provider provenance.
- Treat rich-field additions, removals, or changes as material review changes for refresh and known-review streak detection.
- Google Places fallback reviews may legitimately have no equivalent rich data.

### Validation limits

- Enforce the following backend limits independently for `details`, `translated_details`, and `images`:
  - At most 32 fields per details map.
  - At most 80 characters per normalized detail key.
  - At most 1,000 characters per scalar string value.
  - At most 20 scalar items per list and 250 characters per string list item.
  - At most 16 KiB of normalized UTF-8 JSON per details map.
  - At most 20 images per review and 4,096 characters per image URL.
- Treat duplicate normalized keys, non-finite numbers, unsupported shapes, invalid URLs, and exceeded limits as malformed for that rich-data section rather than truncating silently.
- Validate `details`, `translated_details`, and `images` independently so one malformed section does not prevent the base review or another valid rich-data section from being accepted.

### Snapshot semantics

- Distinguish four states for each rich-data section:
  - Omitted field: preserve the previous valid snapshot because the provider did not supply that section.
  - Valid nonempty field: replace the previous snapshot.
  - Valid empty `{}` or `[]`: explicitly clear structured data or deactivate previous images.
  - Present but malformed field: preserve the previous valid snapshot while still accepting the base review.
- For a new review with malformed rich data and no prior valid snapshot, store no data for that section.
- Record a safe diagnostic reason and provider/review identifier for malformed data without logging full image URLs.

### Persistence

- Add canonical JSONB fields for structured and translated details.
- Add ordered review-image persistence with review, provider/origin, URL, position, first/last-seen timestamps, and active state.
- Do not store image binaries in PostgreSQL.
- Keep provider-specific source data attributable and avoid overwriting richer SerpApi fields with missing fallback values.
- Increment `review_corpus_version` exactly once per committed provider-page transaction when any visible structured detail, translated detail, active image set, image position, or rich review origin changes. Multiple rich changes in the same page still produce one increment.
- Do not increment the corpus version for omitted or malformed sections that preserve existing state, normalized no-op updates, or topic-only changes.
- Include rich fields in deletion, deduplication, refresh, and migration tests.

### Translated details

- Always return both `details` and `translated_details`; the original details remain authoritative for field existence and ordering.
- Use a translated value for display only when its normalized key uniquely matches an original key and its scalar/list shape is compatible.
- Do not override a nonempty original with an empty translated value. On collisions or type mismatches, display the original value.
- Retain translated-only keys in `translated_details`, but do not add them independently to the primary review-card display in BL-009.

### API and review cards

- Return structured details and ordered image metadata in review responses.
- Return active images only, ordered by provider position with a stable database-ID tie breaker.
- Render a compact recognized-field order first: order/service type, meal type, price, food, service, atmosphere, and recommended dishes.
- Render remaining safe scalar/list fields through a generic label/value component.
- Prefer translated labels/values when available while retaining the original data.
- Show review images in an optional horizontal gallery with lazy loading, broken-image fallback, direct review/source access, and accessible labels.
- In the review header, show the overall numeric rating followed by the same number of visible stars: `1 ★`, `3 ★★★`, and `5 ★★★★★`. Do not use a single star merely as a suffix.
- Expose one concise accessible label such as `3 out of 5 stars` for the overall rating and hide the decorative repeated stars from assistive technology so the value is not announced twice.
- Keep structured sub-ratings such as food, service, and atmosphere as plain numeric detail values; the repeated-star rule applies only to the review's overall rating.
- Do not infer missing details, image captions, or restaurant attributes with the LLM.

### Remaining review-card layout refinement

- Replace the full-width two-column definition list with one compact responsive metadata grid so short rich-data values do not leave a large empty region inside the review card.
- Keep a single subtle shared background for the details section; do not turn each field into a separate card or dashboard tile.
- Place each label above its value and retain the existing recognized-field order.
- Use three columns on desktop, two columns on tablet and normal phone widths, and one column only when the viewport is too narrow for two readable columns.
- Let long values such as recommended dishes, dietary notes, parking, and accessibility span the full grid row when needed.
- Use content-driven height with no fixed or minimum height. Target approximately 14–16px section padding and 8–12px row spacing.
- Keep the surrounding review cards compact as well: approximately 14–16px card padding, 12px between cards, 8px between header metadata items, and a readable 24px review-body line height. Let the shared topic/review column expand to `max-w-6xl` instead of the old `max-w-4xl` on wide desktop panes so outer side gutters do not dominate the layout. Preserve responsive 16–24px page padding and 44px touch targets for actions.
- Do not render the details container when there are no displayable details. Keep the review-image gallery separate from the metadata grid.
- Preserve safe generic rendering, translated-value selection, keyboard behavior, and horizontal-overflow protection at every breakpoint.

### Image lifecycle

- Apply image replacement or removal only to a review that is actually present in the current provider page and has a present, valid `images` snapshot.
- For `images: []`, deactivate every active image belonging to that provider review origin.
- For a valid nonempty snapshot, upsert its URLs, update positions after reordering, and deactivate previously active URLs missing from that snapshot.
- Preserve existing images when a review is absent from the provider page or its `images` field is omitted or malformed.
- Deduplicate repeated URLs within a valid snapshot while preserving the first occurrence and position.
- Associate images with their provider review origin. Deleting an origin cascades its images, and deleting a canonical review cascades its origins and images.

### Safety and lifecycle

- Allow only provider-returned HTTPS image URLs whose normalized hostname exactly equals `lh3.googleusercontent.com`, `lh4.googleusercontent.com`, `lh5.googleusercontent.com`, or `lh6.googleusercontent.com`.
- Do not use wildcard/suffix matching: a host such as `example.lh3.googleusercontent.com` is not allowed. Reject credentials, IP-literal hosts, and nonstandard ports. Normalize hostname case, IDNA, and a trailing dot before exact matching.
- Do not initially allow SerpApi-hosted image URLs; add a narrowly scoped exact host and path only after a captured Google Maps Reviews API fixture demonstrates that it is required.
- Prevent structured values from becoming executable markup.
- Expect remote image URLs to expire or become unavailable.
- Render direct images with `loading="lazy"`, `decoding="async"`, `referrerpolicy="no-referrer"`, and neutral labels such as `Review photo 1`.
- Restrict the frontend Content Security Policy `img-src` to the exact supported hosts, use `rel="noopener noreferrer"` for external image/source links, and show clear Google/SerpApi provider attribution.
- Document that direct third-party image loading exposes the viewer's IP address to the image host, and avoid logging full image URLs.
- Review provider attribution, caching, proxying, and retention requirements before any image-download or image-proxy feature.

### Completion notes

- Added migration `0007_review_rich_data.py` with canonical and provider-provenance JSONB fields plus ordered, cascading review-image metadata.
- Added independently validated SerpApi `details`, `translated_details`, and image snapshots with omission/malformed preservation, explicit-empty clearing, strict URL hosts, and safe diagnostics.
- Added material rich-data detection, image lifecycle updates, and once-per-provider-page corpus-version invalidation.
- Added backward-compatible API fields and review-card details/image gallery rendering with translated display values, broken-image handling, and production image CSP.
- Added backend rich-data/parser/material-change coverage and frontend rendering coverage.
- Refined the rich-detail card into an adaptive compact metadata grid with full-row long values and accessible repeated-star rating display.

### Acceptance criteria

- The example fields shown by Google Maps can be preserved when SerpApi supplies them.
- Unknown detail keys survive ingestion and render generically.
- Field disappearance or image-set changes are detected as material updates.
- Material rich-data changes increment the BL-008 corpus version once per committed provider page and make prior saved-review cursors stale.
- Images retain provider order and failures do not break the review card.
- Omitted or malformed rich sections preserve the previous valid snapshot, while valid empty snapshots clear or deactivate it.
- Fallback reviews render normally without rich fields.
- API schemas remain backward compatible through empty/default rich-data collections.
- On desktop, short structured fields use the available width in a compact three-column grid without disproportionate empty box space; the grid adapts to two and then one column as width requires.
- Long fields span the grid cleanly, an empty details section renders no container, and mobile layouts introduce no horizontal overflow.
- The overall review rating renders a number plus that number of visible stars, while assistive technology receives one nonduplicated `N out of 5 stars` label; structured sub-ratings remain plain numeric values.
- Tests cover complete, partial, unknown, translated, malformed, missing, empty, changed, reordered, and removed rich data; validation boundaries and normalized-key collisions; image-host rejection; origin deletion cascades; and once-per-page corpus-version invalidation.

## BL-010 — Private Oracle and Tailscale deployment

- Status: `Proposed`
- Area: Private hosting, networking, operations, and family access
- Priority: Future
- Detailed design: [Design document, Section 21](design_doc.md#21-planned-feature-private-oracle-and-tailscale-deployment)

### Goal

Run the containerized web application continuously on the Oracle VM while keeping it private to the family Tailnet and allowing the Oracle-hosted FastAPI backend to reach the home Linux LLM without exposing the LLM or application to the public internet.

This item is intentionally sequenced after BL-007 through BL-009 so feature development can continue locally first.

### Target topology

```text
Family browser / installed Home Screen app
                    │
              Tailscale HTTPS
                    │
             Oracle VM Tailnet
          reverse proxy → frontend/API
                    │
       PostgreSQL on private Docker network
                    │
              Tailscale only
                    │
       Home Linux OpenAI-compatible LLM
```

### Network and access rules

- Join the Oracle VM to the Tailnet with a dedicated, tagged Tailscale identity.
- Keep PostgreSQL reachable only on the Docker network.
- Bind application ingress to loopback/private interfaces and publish it through a Tailnet-only HTTPS endpoint.
- Do not open the app, API, PostgreSQL, or LLM ports to the public internet.
- Apply Tailscale grants/ACLs so approved family devices can reach the app and only the Oracle API identity can reach the LLM port.
- Use one same-origin HTTPS hostname for the frontend and `/api` reverse proxy where practical.
- Keep Oracle cloud firewall rules and host firewall rules deny-by-default except for required administration/Tailscale traffic.

### Deployment and operations

- Use `docker/compose.yaml` plus `docker/compose.prod.yaml`, immutable production images, health checks, restart policies, and no source bind mounts.
- Run Alembic migrations as an explicit deployment step before switching the application version.
- Store secrets outside Git and do not copy the development `.env` unchanged.
- Back up the PostgreSQL volume and perform a restore test before family rollout.
- Add structured request IDs, provider-operation logs, disk/health monitoring, and a documented rollback procedure.
- Keep one API replica until BL-007 has shared concurrency protection.
- Make LLM-dependent filtering fail gracefully while the home Linux machine is offline.

### Home Screen and future native clients

- The existing responsive PWA remains the first family client.
- Tailnet access is required for both browser and installed Home Screen use.
- A future native iOS client can call the same authenticated/private API without changing review-provider or LLM architecture.
- App Store or TestFlight distribution is not required for this deployment.

### Acceptance criteria

- An approved Tailnet device can load the HTTPS application and use the API.
- A device outside the Tailnet cannot reach the application.
- The Oracle API can reach the home LLM over Tailscale, but no public client can reach the LLM directly.
- PostgreSQL has no public host port.
- Reboots restore the application automatically without losing the named database volume.
- Backup restoration, migration, health checks, rollback, secret replacement, and LLM-offline behavior are documented and tested.

## BL-011 — Google relevance-first review ingestion and local sorting

- Status: `Done`
- Area: Review synchronization, provider ordering, persistence, filtering, and pagination
- Priority: High
- Detailed design: [Design document, Section 22](design_doc.md#22-planned-feature-google-relevance-first-review-ingestion)

### Goal

Replace the primary `newestFirst` review-ingestion walk with SerpApi's `qualityScore` order so the same paid requests both collect canonical review data and preserve Google's most-relevant ordering. Continue deriving most recent, oldest, highest rated, and lowest rated locally from saved publication timestamps and ratings.

This feature does not calculate relevance. SerpApi and Google do not return a numeric quality score for each review. The application stores the one-based ordinal position of each review in the returned `qualityScore` sequence and calls it `google_relevance_rank` or `relevance rank`, never `quality score`.

### Verified existing data

- The SerpApi restaurant-review normalizer reads `iso_date` first and stores it in the existing timezone-aware `reviews.publication_timestamp` column.
- It stores `iso_date_of_last_edit` separately as `last_edit_timestamp`.
- Existing `recent` and `oldest` SQL sorts already use `publication_timestamp` descending/ascending with nulls last and review ID as the final tie breaker.
- Ratings are already stored canonically and power the existing high/low sorts.
- A read-only development database check on 2026-08-02 found 357 of 386 canonical reviews with publication timestamps. The primary saved restaurant datasets checked—Little Pizza, New Sing Sheng Kitchen, Pizza sam, Om Wok, Ming Wok, Chung Ki Wa, and Sun Hing—had timestamps for every stored review. The 29 missing timestamps were contributor-history records; null-last behavior remains required.

The live counts are verification evidence, not a permanent schema invariant. Provider fields remain nullable and tests must cover missing dates.

### Provider and cost behavior

- Initial synchronization requests `engine=google_maps_reviews`, the Google Place ID, configured language, and `sort_by=qualityScore`.
- The initial page normally contains eight reviews; later pages accept up to 20 and continue through `serpapi_pagination.next_page_token`.
- Assign relevance ranks directly from the provider array order and continue them across pages. Bound collection by provider records processed and report newly stored canonical reviews separately so deduplication cannot unpredictably expand the approved request count.
- A 50-review target normally requires approximately four successful searches: 8, then up to 20, 20, and the remainder.
- These searches replace the current initial newest-first searches. Do not run both sort walks during initial collection.
- Cached SerpApi responses retain their existing zero-billed accounting; uncached responses use the shared BL-007 reservation and settlement rules.
- Bind every provider cursor to place, provider, language, and provider sort. Never reuse a `qualityScore` cursor with `newestFirst`.
- SerpApi documents that total results may vary with sort mode. Treat relevance ingestion as an ordered snapshot, not proof of complete Google review coverage.

### Persistence contract

Add provider-specific relevance membership without duplicating canonical review content. The preferred normalized structure is `review_relevance_ranks` with:

- Place ID
- Canonical review ID
- Provider name
- Provider sort (`qualityScore`)
- Language code
- Snapshot/generation ID
- One-based rank
- Fetched timestamp

Enforce uniqueness for review membership and rank within a place/provider/language/snapshot. Provider collection state records the active completed relevance snapshot, its ranked count, next provider cursor, next rank, fetch timestamp, stop reason, and associated provider operation.

Review rows continue storing rating, text, author, publication timestamp, edit timestamp, rich data, images, and canonical/source identities exactly once. When relevance and newest-first walks return the same Google review ID, update/deduplicate the same canonical review and attach ordering metadata separately.

### Snapshot and failure semantics

- Initial sync may activate the first usable relevance snapshot after the confirmed target completes or provider pagination ends.
- `Refresh relevance` starts from rank 1 and builds a replacement generation.
- Keep the last completed relevance snapshot readable while a replacement is running.
- Atomically switch the active snapshot; never expose a mixture of rank generations.
- A malformed response, cancellation, cursor expiry, provider failure, or insufficient budget must preserve the previous completed snapshot.
- Canonical review inserts or material updates from successfully processed pages may still commit under the existing per-page durability rules even when a replacement rank snapshot is not activated.
- Activating or extending relevance ordering increments `review_corpus_version` once per logical committed ordering change and invalidates saved-review cursors.
- Cursor-expiry recovery requires a new idempotency key and confirmation, restarts `qualityScore` at rank 1, and deduplicates without discarding canonical reviews.

### Local sorting contract

Extend `ReviewSort` with `relevant`. The allowlisted SQL definitions become:

- `relevant`: active relevance rank ascending/nulls last, publication timestamp descending/nulls last, review ID ascending
- `recent`: publication timestamp descending/nulls last, review ID ascending
- `oldest`: publication timestamp ascending/nulls last, review ID ascending
- `rating_high`: rating descending/nulls last, publication timestamp descending/nulls last, review ID ascending
- `rating_low`: rating ascending/nulls last, publication timestamp descending/nulls last, review ID ascending

Most recent and oldest always mean review publication time. Do not use last edit, first fetched, last seen, relevance fetched, or operation completion time. Exact-star filtering happens before ordering. Semantic filters decide membership independently and then apply the requested SQL order; changing only sort preserves selected IDs and does not rerun the LLM.

Selecting `Google most relevant` after its snapshot exists is a PostgreSQL query. It does not call SerpApi. Reviews discovered outside the active relevance response have a null rank and appear after ranked reviews, ordered by publication timestamp descending and review ID.

### Completeness reconciliation

Add a separate explicit `Check for new reviews` action using `newestFirst` for completeness and recent-change discovery:

- Require the normal BL-007 estimate and confirmation.
- Maintain a separate sort-bound cursor/state from relevance collection.
- Apply BL-001's ten-known-unchanged shortcut.
- Upsert/deduplicate the same canonical review records.
- Do not assign a relevance rank to reviews not returned by `qualityScore`.
- Leave the active relevance snapshot unchanged.
- Report new, updated, unchanged, request, and stop-reason counts.

The existing generic `Refresh` UI must be separated or renamed so users understand the difference between `Refresh relevance` and `Check for new reviews`.

### API and backend changes

- Add `relevant` to list/filter request and response enums.
- Return `relevance_available`, `relevance_fetched_at`, and optionally ranked count in the restaurant review response.
- Keep `GET .../reviews` and deterministic `POST .../reviews/filter` provider-free.
- Change initial sync and relevance load-more operations to `qualityScore`.
- Add or adapt an explicitly confirmed newest-first reconciliation operation; do not overload a saved-review sort change to start it.
- Store provider sort in collection state and provider-operation result metadata.
- Change the default configured primary provider sort from `newestFirst` to `qualityScore` and validate configured values.
- Continue using opaque, corpus-versioned keyset cursors. Relevant cursors include the last rank, fallback publication timestamp, and review ID and are rejected after snapshot activation changes the corpus version.

### Frontend behavior

- Add the concise `Most relevant` option before the four existing sort options only when an active relevance snapshot exists. Do not render a long disabled placeholder inside the native select; it widens the control and native browsers gray disabled options inconsistently.
- Use it by default when the restaurant has an active relevance snapshot.
- Historical restaurants without a relevance snapshot default to `Most recent`, omit the unavailable relevance option, and show the concise non-error status `Relevance not fetched` beside the restaurant metadata.
- Reset returns to the best available default rather than selecting a relevance mode that has no data.
- Saved sort changes remain immediate and free.
- Keep these actions visually and semantically distinct:
  - `Show more saved reviews` — PostgreSQL only
  - `Fetch more relevant reviews` — resumes `qualityScore`, provider cost
  - `Refresh relevance` — restarts `qualityScore`, provider cost
  - `Check for new reviews` — starts/resumes `newestFirst`, provider cost
- Every paid action uses existing preflight choices, request estimates, explicit confirmation, idempotency keys, progress polling, cancellation, and stable recovery errors.
- Show relevance age/ranked count in the developer/provider-action surface. Do not display internal rank on review cards as a quality judgment.

### Migration and rollout

- Existing review rows remain valid and initially have no active relevance membership.
- Preserve existing `newestFirst` cursors with their sort tag; do not migrate them into relevance cursors.
- Roll out schema/provider changes before making `relevant` the frontend default.
- After deployment, a restaurant receives relevance ordering on its next explicit initial sync or `Refresh relevance`; no automatic paid backfill is allowed.
- The migration downgrade removes relevance metadata without deleting canonical reviews.

### Completion notes

- Added migration `0009_relevance_snapshots` with sort-bound collection state and snapshot-scoped `review_relevance_ranks`; existing canonical reviews and legacy newest-first cursors remain intact.
- Changed the configured primary SerpApi sort to validated `qualityScore`, persisted provider-array ordinal ranks independently of canonical review content, and added active/pending relevance snapshot lifecycle state.
- Added the free `relevant` local sort, rank-null fallback ordering, relevance availability metadata, and automatic best-available UI default without treating rank as a quality score.
- Added explicit `Check for new reviews` newest-first reconciliation, separate provider cursor state, and action labels that distinguish relevance refresh/continuation from free saved paging.
- Replacement snapshots preserve a previous active snapshot until a target/end boundary succeeds; initial successful prefixes activate as partial snapshots and can be extended.

### Acceptance criteria

- Initial `qualityScore` ingestion assigns continuous one-based ranks across page boundaries and does not make a duplicate newest-first walk.
- The same Google review returned by either provider sort maps to one canonical review.
- `relevant` reproduces the saved provider order for ranked rows and deterministically places unranked rows afterward.
- Recent/oldest sorts use saved publication timestamps; high/low use saved ratings; all four make zero provider and LLM calls.
- Exact-rating and semantic membership compose correctly with all five sort modes.
- Relevance replacement is atomic and failures preserve the last completed snapshot.
- Cursor state cannot cross place, language, provider, or provider-sort boundaries.
- Relevance activation invalidates stale saved-review cursors exactly once per logical ordering change.
- Newest-first reconciliation discovers/deduplicates reviews without modifying saved relevance ranks.
- Historical restaurants without relevance data have an explicit fallback state.
- Tests cover 8/20 pagination boundaries, rank ties/missing ranks, null publication dates, provider cursor expiry, operation cancellation, partial page durability, budget exhaustion, idempotency, snapshot replacement, corpus-version cursors, responsive controls, and zero-cost saved sorting.

## BL-012 — Google review summary and local dish summary

- Status: `Done`
- Area: Restaurant insights, Google Places, local LLM synthesis, persistence, and attribution
- Priority: Medium
- Detailed design: [Design document, Section 23](design_doc.md#23-planned-feature-google-review-summary-and-local-dish-summary)

### Goal

Add two clearly separate restaurant insights:

1. Google's official AI-generated review-summary backend capability, retained behind its feature gate for a possible future UI. It is not currently exposed in the frontend.
2. A saved local dish-summary paragraph generated on demand from the review texts currently displayed after the user's active filtering and sorting.

The UI and API must never merge the two summaries, apply Google's attribution to the local paragraph, or imply that Google generated or endorsed the local result.

### Verified provider boundary

- Google Places API (New) exposes `reviewSummary` on Place Details (New). It is generated solely from user reviews, may mention specific foods, is not guaranteed for every place, and is billed under the Place Details Enterprise + Atmosphere SKU.
- Request only `reviewSummary.text`, `reviewSummary.disclosureText`, `reviewSummary.reviewsUri`, and `reviewSummary.flagContentUri` plus the minimum identity field needed by the adapter.
- SerpApi's documented `place_results.user_reviews.summary` is an array of selected review excerpts, not the same contract as Google's official AI `reviewSummary`. Do not label those excerpts as a Google review summary.
- The local dish summary uses review texts supplied by the current client from the currently displayed review list. It makes no Google or SerpApi request and does not use Google's official summary as model input.
- Current Google Places policy generally prohibits prefetching, caching, or storing Places content beyond listed exceptions such as Place IDs. The official Google summary text, disclosure, and action URIs are transient display data and are not written to PostgreSQL, browser storage, a service-worker cache, logs, or operation-result JSON.

### Explicit acquisition and generation

- Never fetch the Google summary during autocomplete, free-text search, restaurant selection, review-list loading, ordinary review refresh, filtering, or sorting.
- Do not currently expose a Google review-summary action in the frontend. The confirmed backend endpoint and attribution validation remain dormant for a future UI.
- Run that request through the existing confirmed, idempotent, persisted operation pattern with `provider=google_places` and `operation_type=google_review_summary`. Do not charge it against the SerpApi allowance. Use the independent UTC calendar-month `GOOGLE_REVIEW_SUMMARY_MONTHLY_REQUEST_BUDGET=25` safety budget and `GOOGLE_REVIEW_SUMMARY_MAX_CONCURRENCY=1`.
- Return a successful Google summary directly to the requesting client for transient in-memory display. A valid response without `reviewSummary` is an `unavailable` result, not a provider failure. Persist only non-content accounting and outcome metadata.
- Generate the local paragraph only when the user presses `Generate summary` or `Replace summary`. Search, selection, review synchronization, load-more, filter changes, sort changes, and navigation never invoke the local LLM automatically.
- Local generation uses one request lifecycle and creates no provider reservation, background job, or local operation row. The local LLM response is streamed through the backend for progressive rendering.

### Local review selection and prompt

- The numeric review-count input defaults to `10`. The user may request a larger number up to `LOCAL_DISH_SUMMARY_MAX_REVIEWS` (default `50`), but the frontend never sends more reviews than are currently displayed.
- The backend trims Unicode whitespace before applying `LOCAL_DISH_SUMMARY_MAX_REVIEW_CHARS=4000` and `LOCAL_DISH_SUMMARY_MAX_TOTAL_CHARS=20000`. It also rejects a complete UTF-8 request body larger than `LOCAL_DISH_SUMMARY_MAX_REQUEST_BYTES=131072` with `422 DISH_SUMMARY_INPUT_TOO_LARGE`; it never silently omits selected reviews.
- Apply the active filters and sort first, preserve that visible order, and send the first requested number of displayed review texts. If the requested count exceeds the currently displayed count, tell the user to show more saved reviews; do not silently include unseen reviews.
- Send review text only. Do not send canonical review IDs, ratings, dates, reviewer metadata, profiles, avatars, locations, restaurant metadata, or filter/sort context.
- The model returns one concise plain-text paragraph rather than structured JSON. Ask it for exactly three concise sentences totaling about 75 words and never more than 80, prioritizing which dishes or drinks reviewers most often praise while retaining important mixed or negative feedback, combining obvious aliases, avoiding objective `best`/`worst` claims, and saying plainly when the supplied texts contain too little dish information.
- Treat review text as untrusted evidence and instruct the model to ignore instructions embedded inside it.
- Bound the number of review texts, each text's length, total request size, and returned paragraph length. Reject an empty or oversized model response.

### Persistence contract

Add one nullable text column to `places`:

```text
llm_dish_summary text nullable
```

There is one current local paragraph per restaurant. A successful generation atomically replaces any previous value. A failed or unavailable LLM call returns an error and leaves the existing saved paragraph unchanged. No separate summary, input, evidence, snapshot, run, or cache table is added, and the submitted input reviews are not copied into a new database record.

The Google proxy response remains transient. Its localized text, localized disclosure, and action URIs stay separate. For the initial US/English scope, accept returned `reviewsUri` and `flagContentUri` only when they use HTTPS and the exact hostname `www.google.com`; the fixed About link uses `support.google.com`. Reject all other hosts, do not embed upstream HTML, and render links with a restrictive referrer policy. The persisted Google provider-operation row contains accounting and stable outcome metadata only, never response content.

### API contract

- The existing restaurant-detail response includes nullable `llm_dish_summary` and never contacts the LLM while reading it.
- `POST /api/v1/restaurants/{place_id}/dish-summary` accepts a bounded `review_texts: string[]`, calls the configured local LLM synchronously, stores the returned paragraph on the restaurant, and returns `200` with `{"summary": "..."}`.
- `POST /api/v1/restaurants/{place_id}/dish-summary/stream` accepts the same request and returns newline-delimited `delta`, terminal `done`, or terminal `error` events. It requests OpenAI-compatible upstream streaming with thinking disabled, forwards text deltas immediately, and stores the normalized paragraph only before emitting `done`.
- The local endpoint does not require review IDs and does not attempt to reconstruct or verify the client's active review filters. It trusts the current client to submit the displayed review texts.
- If the local LLM is missing, unreachable, times out, or otherwise fails, return `503` with stable code `LLM_UNAVAILABLE` and the message `The local LLM isn't available. Try again later.` Do not erase or replace the prior saved paragraph.
- `POST /api/v1/restaurants/{place_id}/insights/google-review-summary` remains the separate confirmed synchronous Google request and returns the transient typed provider summary or unavailable result. Google idempotency prevents duplicate billing while an active request is running, but completed content cannot be replayed because it is not stored. Reusing a completed matching key returns `409 GOOGLE_SUMMARY_REPLAY_UNAVAILABLE`; parameter mismatches retain the ordinary idempotency-conflict response.

### Frontend behavior

- Place the saved local dish summary and its controls directly above review topics and the review list.
- Show a numeric `Reviews to include` input defaulting to `10`, bounded by the configured maximum and the number of reviews currently displayed.
- On wide screens, show the count input and summary action in the same header row as `Local dish summary`, with the paragraph beneath; allow the controls to wrap or stack on narrow screens. Omit explanatory copy about using the first currently loaded reviews.
- The initial action is `Generate summary`; after a saved paragraph exists it becomes `Replace summary`.
- The generated paragraph remains the restaurant's saved summary until a later successful replacement. Changing filters, sort, pages, or stored reviews does not automatically clear or regenerate it.
- While generation is pending, disable duplicate submission and render incoming text deltas with a subtle activity indicator. On a terminal error or disconnect, restore the previous summary, show the inline error, and leave the saved database value unchanged.
- Label the paragraph `Local dish summary` or equivalently clear local wording. Do not use Google's disclosure, logo, attribution, or visual treatment on it.
- Keep the review list in an explicitly shrinkable single-column grid (`minmax(0, 1fr)`) and give review cards a zero minimum width so rich review content cannot enlarge the restaurant pane.
- A review's photo gallery may scroll horizontally inside its own card, but its intrinsic image-row width must never widen the card, review pane, or page.
- Do not render a Google `Review summary` container, action, or attribution until the dormant feature is explicitly reintroduced in the frontend.

### Logging, privacy, and safety

- The application may log the local LLM input review texts and returned paragraph. These logs are not relational input storage, but they are persistent data and must follow the deployment's normal size limits, access controls, rotation, and retention policy.
- Never log Google's official summary prose, disclosure, action URLs, or raw response body.
- Do not send reviewer profile/history, avatar, location, inferred demographic data, or Google official summary content to the local LLM.
- The local paragraph summarizes reviewer opinions; it is not professional, allergy, health, dietary, availability, or menu advice.
- Keep separate `GOOGLE_REVIEW_SUMMARY_ENABLED` and `LOCAL_DISH_SUMMARY_ENABLED` gates. Default both off in production until provider-term and attribution review is complete; development/test may enable them explicitly. `LOCAL_DISH_SUMMARY_LOG_CONTENT=false` by default; metadata-only logs contain restaurant ID, input count/characters, duration, outcome, and error code.

### Acceptance criteria

- Opening, searching, selecting, filtering, sorting, paging, and refreshing a restaurant make no Google-summary or local-summary request.
- One explicit Google action requests only the allowlisted Place Details fields, is independently cost-accounted, and returns transient content without persisting it.
- Google summary absence is a valid unavailable state; SerpApi snippets are never presented as Google's official summary.
- The local control defaults to the first 10 currently displayed reviews in their current filtered and sorted order.
- The user can request more displayed reviews up to the configured limit; unseen reviews are never silently included.
- The local request sends review texts without review IDs or filter/sort context, makes zero provider requests, and progressively renders one plain-text paragraph from the local LLM.
- Successful local generation replaces `places.llm_dish_summary`; no input-review, evidence, snapshot, run, or cache rows are created.
- Local LLM input and output may appear in bounded rotating logs, but submitted inputs are not duplicated into a database table.
- An unavailable or failed LLM call returns the defined error, preserves the previous saved paragraph, and does not affect normal review browsing.
- Tests cover default/custom review counts, visible-order selection, count greater than currently displayed, input/output bounds, plain-text generation, replacement, persistence across reopening a restaurant, failure preservation, prompt injection language, responsive controls, and zero implicit calls.
- Responsive browser tests render a review containing at least seven fixed-width photos and verify that the review pane and card do not overflow while the photo strip itself remains horizontally scrollable. Component tests also protect the grid/card/gallery shrink constraints.
- Tests also cover Google presence/absence, exact attribution rendering, malicious hostname rejection, confirmed billing/idempotency, and absence of Google summary content from persistence and logs.

### Completion notes

- Added the `places.llm_dish_summary` migration and local summary endpoint with bounded, synchronous plain-text LLM generation that preserves the prior paragraph on failure.
- Added transient Google Place Details review-summary retrieval with exact `www.google.com` HTTPS action-link validation, explicit `languageCode=en`/`regionCode=US`, independent monthly reservation/accounting, and non-replayable completed idempotency keys.
- Added responsive local dish-summary controls above review topics, visible-order selection from loaded reviews, and backend/frontend regression coverage. The Google endpoint remains intentionally dormant with no frontend action.
- Added OpenAI-compatible local-LLM streaming through an NDJSON backend endpoint; the UI renders deltas immediately and persistence occurs only after the terminal paragraph validates successfully.
- Constrained rich review cards to the available pane width and kept multi-photo overflow inside the gallery. Added a seven-photo responsive regression fixture that checks page, pane, card, and gallery geometry across desktop, phone, and tablet layouts.
