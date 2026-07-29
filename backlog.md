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
