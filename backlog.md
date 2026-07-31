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

- Status: `Proposed`
- Area: Reviewer context
- Priority: Future
- Detailed design: [Design document, Section 17](design_doc.md#17-deferred-feature-on-demand-reviewer-context)

### Goal

Let the user explicitly load a reviewer's public Google Maps contribution context and compare the current rating with the reviewer's observed overall and restaurant-category rating history.

This is contextual information, not a credibility, truthfulness, or quality verdict. No public category history observed must be represented as unavailable evidence rather than a negative signal.

### Intended interaction

- Show `Load reviewer context — may use 1 SerpApi search` only when the review has a usable SerpApi contributor ID.
- Never fetch contributor history during restaurant sync, page load, hover, or background work.
- Check for a permitted reusable context snapshot before making a live request.
- Disclose and confirm the potential SerpApi search before an uncached lookup.
- Open the context in a drawer or modal.
- Fall back to the public Google Maps contributor link when enrichment is unavailable.

### Context and baseline

The first version may show:

- Public contributor name, avatar, profile link, Local Guide status, and contribution counts
- Number of public reviews observed in the returned sample
- Observed overall mean rating
- Observed restaurant and normalized-category review counts
- Observed mean rating by normalized restaurant category
- Difference between the current rating and the reviewer's observed overall/category means
- A small linked sample of relevant public reviews

Prefer transparent deterministic aggregates with sample-size disclosure and shrinkage over an LLM-generated score.

### Cost, privacy, and storage constraints

- One contributor lookup is a separate SerpApi search and must use the global atomic budget control.
- Bulk reviewer enrichment is out of scope.
- Do not send contributor profiles or histories to the LLM.
- Do not infer or score sensitive traits, personal identity, home location, or travel patterns.
- Prefer derived aggregates and source identifiers over retaining complete copied histories or exact place coordinates.
- Define retention, refresh, deletion, attribution, and shared-contributor behavior before implementation.
- Keep the feature disabled for public release until provider terms and privacy implications are reviewed.

### Acceptance criteria

- Contributor history is fetched only after an explicit click and cost confirmation when required.
- Concurrent clicks for the same contributor produce at most one upstream search.
- Cached/retained context can be read without an upstream request.
- Missing history is displayed as unavailable, not as zero expertise.
- Context calculations disclose observed sample sizes.
- Reviewer context does not automatically change review filtering, ordering, or visibility.
- Provider usage tracks contributor searches separately while enforcing the shared SerpApi allowance.
- The user can delete locally retained context.

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
- Provider relevance sorting
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
- `Jack`
- `David`
- `Eric`

`Any reviewer label` is the default and performs no label-related LLM inference.

### Backend-owned options

Define the initial name choices once in the backend:

```python
REVIEWER_LABEL_OPTIONS = {
    "jack": "Jack",
    "david": "David",
    "eric": "Eric",
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
  "reviewer_label": "jack",
  "content_filter": "mentions outdoor seating",
  "sort": "recent"
}
```

The fields are independent:

- Exact rating and sort use the deterministic controls in `BL-004`.
- Reviewer label is null or one of `jack`, `david`, and `eric`.
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
- Added `GET /api/v1/reviews/filter-options` with backend-owned Jack/David/Eric reviewer-label options.
- Added `POST /api/v1/restaurants/{place_id}/reviews/filter` for unified deterministic, reviewer-label, and content filtering.
- Added validated backend request schema for exact rating, reviewer-label key, content filter, and allowlisted sort.
- Reused deterministic exact-rating SQL filtering and allowlisted sorting from `BL-004`.
- Added isolated reviewer-label LLM batching that sends only target label, canonical review ID, and stored author display name.
- Added conservative reviewer-label prompt rules: Jack does not match Jackie/Jackson/Jacqueline/John; Dave may match David; Erik may match Eric; uncertain entries are excluded.
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

- The dropdown always offers Any, Jack, David, and Eric after reviews exist.
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

- Status: `Ready`
- Area: Provider budgets, synchronization safety, and duplicate-request protection
- Priority: High
- Detailed design: [Design document, Section 18](design_doc.md#18-planned-feature-cost-and-concurrency-protection)

### Goal

Prevent simultaneous users, browser retries, or requests for different restaurants from exceeding the configured SerpApi allowance or starting duplicate paid work.

The existing per-place PostgreSQL advisory lock remains useful, but it protects only overlapping synchronization for the same restaurant. This item adds global, cross-request accounting and idempotency.

### Required behavior

- Reserve estimated SerpApi searches atomically before starting a synchronization, refresh, load-more operation, or future reviewer-context lookup.
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

### Acceptance criteria

- Two simultaneous operations cannot reserve the same last unit of budget.
- Requests for different restaurants respect the same global allowance.
- Duplicate retries with the same idempotency key do not create another paid operation.
- Same-place concurrent mutations produce at most one active sync.
- Reservation settlement records successful, cached, failed, and released units.
- Crashed-operation reservations expire safely without silently double-spending.
- Tests cover atomic reservation races, same-place locking, different-place budget contention, idempotent retry, expiration, and settlement.

## BL-008 — Review pagination and load more

- Status: `Ready`
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

- Add an explicit restaurant-scoped load-more operation rather than overloading the local `Show more` action.
- Resume from the latest valid stored provider cursor and request only the user-approved additional target.
- Do not apply the known-unchanged refresh shortcut; load more intentionally walks toward older reviews.
- If the provider cursor expired, offer a confirmed newest-first restart and deduplicate all observed reviews.
- Persist every completed page and updated cursor before requesting the next page.
- Return new-review count, total stored count, request count, stop reason, and the next resumable state.
- Never prefetch an upstream page automatically when the user scrolls.

### Semantic-filter boundary

- Initial BL-008 delivery paginates deterministic stored-review browsing.
- Existing semantic filtering remains bounded to the configured candidate maximum and returns its current complete result set.
- Do not rerun the LLM independently for each visible page.
- If semantic result sets later exceed that bound, add a versioned filter-result session or cache before paginating them.

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

- Status: `Ready`
- Area: SerpApi review ingestion, persistence, API schemas, and review cards
- Priority: High
- Detailed design: [Design document, Section 20](design_doc.md#20-planned-feature-rich-review-data)

### Goal

Preserve and display the richer information Google attaches to individual reviews, including review photos and structured fields such as order type, meal type, price per person, sub-ratings, recommended dishes, dietary details, parking, and accessibility notes.

### Provider ingestion

- Read SerpApi `images`, `details`, and `translated_details` from each review.
- Preserve the raw dynamic label/value maps without assuming every restaurant uses the same keys.
- Normalize only recognized display keys while retaining unknown fields for generic rendering.
- Preserve image order and provider provenance.
- Treat rich-field additions, removals, or changes as material review changes for refresh and known-review streak detection.
- Google Places fallback reviews may legitimately have no equivalent rich data.

### Persistence

- Add canonical JSONB fields for structured and translated details.
- Add ordered review-image persistence with review, provider/origin, URL, position, first/last-seen timestamps, and active state.
- Do not store image binaries in PostgreSQL.
- Keep provider-specific source data attributable and avoid overwriting richer SerpApi fields with missing fallback values.
- Include rich fields in deletion, deduplication, refresh, and migration tests.

### API and review cards

- Return structured details and ordered image metadata in review responses.
- Render a compact recognized-field order first: order/service type, meal type, price, food, service, atmosphere, and recommended dishes.
- Render remaining safe scalar/list fields through a generic label/value component.
- Prefer translated labels/values when available while retaining the original data.
- Show review images in an optional horizontal gallery with lazy loading, broken-image fallback, direct review/source access, and accessible labels.
- Do not infer missing details, image captions, or restaurant attributes with the LLM.

### Safety and lifecycle

- Allow only provider-returned HTTPS image URLs from explicitly supported hosts.
- Prevent structured values from becoming executable markup.
- Expect remote image URLs to expire or become unavailable.
- Review provider attribution, caching, proxying, and retention requirements before any image-download or image-proxy feature.

### Acceptance criteria

- The example fields shown by Google Maps can be preserved when SerpApi supplies them.
- Unknown detail keys survive ingestion and render generically.
- Field disappearance or image-set changes are detected as material updates.
- Images retain provider order and failures do not break the review card.
- Fallback reviews render normally without rich fields.
- API schemas remain backward compatible through empty/default rich-data collections.
- Tests cover complete, partial, unknown, translated, malformed, missing, changed, and removed rich data.

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
