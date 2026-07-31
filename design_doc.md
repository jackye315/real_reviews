# Real Reviews — Design Document

## 1. Project Summary

Real Reviews is a personal, responsive restaurant-discovery and review-filtering web application.

The application will:

1. Suggest restaurants and locations as the user types using Google Places Autocomplete.
2. Search for restaurants using Google Places API (New).
3. Use the selected restaurant's Google Place ID to retrieve a deeper review set from SerpApi.
4. Store normalized reviews in PostgreSQL so previously fetched restaurants do not consume more API requests.
5. Deduplicate reviews when the same review appears through more than one provider.
6. Send review text to a local OpenAI-compatible LLM for content-based filtering.
7. Run the entire development environment in containers.

Google Places will be the source of restaurant identity and discovery. SerpApi will be the primary source of review data. Google Places' maximum five-review response will be used only as a fallback.

The first version is a personal research tool. It is not intended for public distribution until the rights to persist, process, and display scraped review content have been reviewed.

Intentionally deferred features and future ideas are tracked in [`backlog.md`](backlog.md), which is authoritative for their status. This document may retain detailed supporting designs, but their presence here does not mean they are implemented. Section 16 tracks known implementation work against the current design.

## 2. Product Boundaries

The LLM may filter reviews using information explicitly present in review text, such as:

- Specific dishes or drinks
- Service quality
- Wait time
- Noise level
- Accessibility
- Dietary needs
- Price or value
- Atmosphere
- Family friendliness

The application will not infer race, ethnicity, or other sensitive traits from reviewer labels, photos, language, profiles, or presumed locations. Author profile information will not be sent to the LLM.

Google and SerpApi review retrieval is best-effort. SerpApi pagination can return substantially more than five reviews, but it does not guarantee that every review displayed by Google will be available.

## 3. User Experience

### 3.1 Initial location request

On the first page load:

1. Display a short explanation that location is used to improve nearby restaurant suggestions.
2. Immediately request browser geolocation.
3. If permission is granted, apply a 5 mile location bias to Google Autocomplete.
4. Keep coordinates only in browser memory.
5. Never persist or log the user's location.
6. If permission is denied, unavailable, or times out, use Google's IP-based location bias.

### 3.2 Restaurant and location suggestions

Use Google's `PlaceAutocompleteElement` from Places API (New). This provides Google's familiar type-ahead dropdown, keyboard navigation, accessibility, localization, and mobile behavior.

When the user selects:

- A restaurant, café, bakery, bar, or food establishment: open its detail view and retrieve reviews.
- A city, neighborhood, postal code, address, or geographic area: search for restaurants within or biased toward its viewport.
- Another type of establishment: offer a "Search for restaurants nearby" action.

If the user submits text without selecting a suggestion, send the text to the backend's Google Text Search flow.

### 3.3 Restaurant details

The restaurant view will show:

- Restaurant name and address
- Google Maps source link and attribution
- Stored review count
- Last fetch time
- Review source and fallback status
- Review fetch progress
- Operation-specific request estimate before an action that may consume SerpApi allowance
- Manual "Load more" and "Refresh" actions

The initial SerpApi fetch target is 50 reviews. The value must be configurable rather than hard-coded.

### 3.4 Review filtering

Review filtering is data-dependent rather than always visible:

1. Selecting a restaurant with no stored reviews shows its details and a primary "Fetch reviews" action. Topic chips, the natural-language filter, reviewer-label dropdown, and deterministic rating/sort controls remain hidden.
2. The first SerpApi review request returns the initial review page and, when Google exposes them, restaurant-specific review topics. The backend persists both before returning the synchronization response.
3. Once at least one review is stored, show the exact-rating control, always-visible reviewer-label dropdown, sort control, and natural-language content filter.
4. Show topic chips only when saved topics exist for that restaurant. Never substitute a global hard-coded topic list.
5. When saved reviews and topics already exist, show them immediately on restaurant selection without making an upstream request. A manual refresh may replace the saved topic snapshot.
6. If reviews exist but SerpApi returned no topics, show the regular filtering controls without a topic row.

The deterministic controls are separate from the LLM filter and never call the LLM:

- Rating: any rating or exactly 5, 4, 3, 2, or 1 star. Selecting 4 stars means `rating = 4`; it never means 4 stars and above.
- Sort: most recent, oldest, highest rated, or lowest rated.
- Default state: any rating, sorted most recent.
- Result feedback: show `filtered_total of total reviews`.
- Reset: restore any rating, any reviewer label, and most recent sorting and clear the content-filter query and active semantic result.

Reviews with a missing rating remain visible only under "Any rating." Reviews with a missing publication timestamp or rating sort after reviews with the requested sortable value. Most recent and oldest refer to the review publication timestamp, not fetch time or edit time.

Changing the exact-rating filter changes the LLM candidate set, so it clears any existing LLM-selected IDs rather than presenting stale semantic results. Changing the reviewer-label selection clears the prior label result and runs the label filter for the new allowlisted value; selecting `Any reviewer label` removes the label constraint without an LLM request. Changing only the sort order preserves active semantic results because membership has not changed. Selecting another restaurant restores any rating, any reviewer label, an empty content query, and most-recent sorting.

Each topic chip represents a topic supplied in the SerpApi Google Maps Reviews response, not a verified restaurant attribute. A topic contains a localized keyword, mention count, and provider topic ID. The UI should label the group "Mentioned in reviews" or "Review topics" so users do not confuse topics with restaurant amenities.

Clicking a topic chip in v1 places its keyword into the existing filter request and filters the reviews already stored in PostgreSQL. It does not make a new SerpApi request. The provider topic ID is retained so a future feature can request Google's exact topic-filtered result set with `topic_id`; such a request would be a separately metered SerpApi search and is not part of the initial implementation.

Reviewer-label filtering is an always-visible dropdown beside the exact-rating and sort controls, not a free-text field and not a mutually exclusive filter mode. The initial options are:

- `Any reviewer label`
- `Jack`
- `David`
- `Eric`

`Any reviewer label` is the default and skips label-related LLM inference. The three named values are hardcoded in one backend mapping that is the source of truth:

```python
REVIEWER_LABEL_OPTIONS = {
    "jack": "Jack",
    "david": "David",
    "eric": "Eric",
}
```

The frontend loads this allowlist from a filter-options endpoint and renders the labels in the dropdown. It must not maintain a second independently hardcoded list. Adding another option later requires extending the backend mapping only. The backend rejects submitted label keys that are not in the allowlist.

Selecting Jack, David, or Eric asks the local LLM whether each stored reviewer display name represents that explicit target name. This is not SQL name matching and does not use `LIKE`, trigram similarity, edit distance, or another fuzzy-string algorithm. SQL is used only to retrieve the selected restaurant's candidate review IDs and stored author display names.

The reviewer-label prompt and payload are isolated from review-content filtering. They contain only:

- Canonical review ID
- Stored reviewer display name
- Selected allowlisted target name

They must not contain review text, rating, publication date, reviewer profile history, location, avatar, or restaurant metadata. Blank or missing display names are excluded before inference and reported as skipped rather than guessed.

The model performs only a label-equivalence decision. It must not classify or infer gender, race, ethnicity, nationality, religion, age, or another personal trait. Reviewer display names are untrusted input; the prompt instructs the model to ignore instructions embedded inside a display name. Uncertain entries are excluded.

The label dropdown and natural-language review-content field are independent and may both be active. When both are active, the backend runs the isolated label and content prompts and intersects their validated review-ID sets. Topic-chip selection populates the review-content filter without changing the selected reviewer-label option.

For review-content filtering, reviews will be sent to the LLM in token-bounded batches. The model will receive only:

- Canonical review ID
- Review text
- Rating
- Publication date

The model will return strict JSON containing selected review IDs. It will not generate replacement review text or classify reviewer identities.

If the LLM is unavailable or returns invalid data, the unfiltered reviews remain visible and the user can retry.

### 3.5 Rich review cards

Implementation is tracked as [`BL-009 — Rich review data`](backlog.md#bl-009--rich-review-data). Section 20 defines the schema, API, and rendering plan; this section defines the product presentation.

When SerpApi supplies the data, each review card may also show:

- Photos attached to that individual review
- Order or service type
- Meal type
- Price per person
- Food, service, and atmosphere sub-ratings
- Recommended dishes
- Dietary, parking, accessibility, and other structured details

SerpApi returns structured review details as a dynamic `details` object and may return localized values in `translated_details`. The application must preserve the raw label/value map, normalize only recognized fields, and render unknown fields generically instead of discarding them. Review images should be displayed from provider-supplied URLs with loading, broken-image, attribution, and source-link handling. Google Places fallback reviews will omit images and structured details when the official Review resource does not provide them.

Reviewer history is not part of the initial review fetch. The deferred on-demand reviewer-context flow is specified in Section 17.

### 3.6 Search-to-reviews workspace

The main interface will use progressive disclosure instead of showing search, provider usage, and reviews as equally prominent dashboard cards.

#### 3.6.1 Initial search state

On first load, the search experience occupies the full viewport:

```text
┌──────────────────────────────────────────────────────────────┐
│ Real Reviews                                           ⚙    │
│                                                              │
│            Find a restaurant                                 │
│            [ Google Places autocomplete                  ]    │
│                         or                                   │
│            [ Free-form restaurant search             ][Go]   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

- Center the product title, explanation, autocomplete, and free-form search in a focused landing view.
- Do not show provider usage, an empty review card, or an empty two-column shell.
- Keep the developer action visually secondary and outside the primary search flow.
- Search errors remain near the relevant input and do not trigger a layout transition.

#### 3.6.2 Search workspace state

After a successful free-form search, transition to a split workspace:

```text
┌──────────────── Search ───────────────┬──────────────── Reviews ──────────────┐
│ Real Reviews                    ⚙    │ Select a restaurant to view reviews   │
│ [ autocomplete                       ]│                                      │
│ [ free-form query               ][Go] │                                      │
│                                      │                                      │
│ Search results                       │                                      │
│ ┌ restaurant result ───────────────┐ │                                      │
│ ├ restaurant result ───────────────┤ │                                      │
│ └──────────────────────────────────┘ │                                      │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

- The left pane contains autocomplete, free-form search, search status, results, and search-result pagination.
- Free-form search displays 10 results per page.
- When browser coordinates are available, backend search results include distance in miles and are sorted by distance within each returned Google result page; otherwise, Google's result order is preserved.
- Search result rows show restaurant rating, rating count, and distance when the data is available.
- The right pane initially shows a quiet selection prompt until the user chooses a restaurant.
- A direct restaurant selection from autocomplete may skip the prompt and open the selected restaurant immediately.
- Search results and the selected restaurant remain independent so selecting a different result replaces only the right pane.
- The left and right panes scroll independently on desktop.

#### 3.6.3 Selected restaurant state

After restaurant selection, the right pane becomes the primary reading surface:

```text
┌──────────────── Search ───────────────┬──────────── Restaurant reviews ────────┐
│ compact search controls              │ name, address, rating, distance, link  │
│                                      │ [Fetch reviews]                        │
│ result list                          │ first-sync empty state                 │
│ • selected restaurant                │                                        │
│ • another restaurant                 │ review cards                           │
│ • another restaurant                 │ review cards                           │
└──────────────────────────────────────┴────────────────────────────────────────┘
```

- Use a fixed or bounded left pane of approximately 360–420 px on large screens; the review pane consumes the remaining width.
- Before the first successful review synchronization, show restaurant metadata, the fetch action, and an explanatory empty state; do not render topic chips or filter controls.
- After reviews are stored, replace the empty state with optional review-topic chips, filter controls, and review cards. Topic chips remain absent when the provider supplied no topics.
- Keep the restaurant header and, when present, review filter controls visible or sticky while the review list scrolls when viewport height permits.
- Give review text and images more horizontal space than search results.
- Preserve the current search query and result list while the user reads or filters reviews.
- The restaurant header shows rating, rating count, and distance when the restaurant was selected from enriched search results.
- Direct autocomplete selections keep the terminating Place Details request Essentials-only. To populate rating and distance in the review header after autocomplete selection, the frontend may perform one explicit backend Text Search for the selected restaurant name/address and match the returned Place ID. This is separate from the autocomplete session and should be understood as a distinct Google Text Search request.
- Provide an explicit `New search` or clear action to return to the full-screen landing state. Errors and empty review results must not unexpectedly collapse the workspace.

#### 3.6.4 Developer drawer

Provider usage will be removed from the normal page layout and moved into an on-demand developer drawer.

- Expose a small gear icon button with accessible label `Developer` in the application chrome.
- Opening it slides a drawer over the right edge without permanently shrinking or reflowing the search/review panes.
- The first drawer content is the existing application-local provider usage data: provider, plan period, successful, cached, and failed request counts.
- Fetch or refresh provider usage only when the drawer opens or the user explicitly refreshes it; it must not be required for the primary search experience.
- The drawer is an extensible diagnostics surface, but health/configuration data should not be added until it has a concrete use.
- Close on an explicit close button or `Escape`; restore focus to the trigger.
- Trap keyboard focus while open, label it as a dialog, and prevent the obscured page from receiving pointer or screen-reader interaction.
- On narrow screens, use a full-width drawer or bottom sheet.
- Allow public production builds to hide the developer trigger through configuration while keeping normal cost-confirmation messages available.

#### 3.6.5 Responsive behavior

The mobile refinement is tracked as [`BL-006 — Mobile-first responsive web app and Home Screen experience`](backlog.md#bl-006--mobile-first-responsive-web-app-and-home-screen-experience). Its backlog status is authoritative.

The web and installed Home Screen experiences use one React application, one component tree, and the same FastAPI endpoints. There is no separately maintained mobile home page. Responsive layout, mobile navigation, and standalone-display adjustments must wrap shared search, restaurant, filter, and review components rather than duplicating their behavior.

Viewport behavior:

- At 1024 px and wider, use the persistent split-pane workspace with independently scrolling search and review panes.
- Below 1024 px, use one primary surface at a time: landing search, search results, or restaurant reviews. A large tablet in landscape may opt into the split layout only when both panes retain usable widths.
- Use dynamic viewport units (`dvh`) with a safe fallback instead of relying exclusively on `100vh`. Account for browser chrome, standalone Home Screen mode, rotation, the iPhone status area, and the bottom Home indicator.
- Add `viewport-fit=cover` only together with explicit `env(safe-area-inset-*)` padding. The application chrome, bottom sheets, and fixed/sticky controls must remain outside unsafe areas.
- Avoid document-wide horizontal overflow at every supported breakpoint. Nested pane scrollers must use `min-height: 0`, clear scroll ownership, and mobile-friendly overscroll containment.

Mobile navigation follows a list/detail flow:

```text
landing search
  ├─ successful free-form search → search results
  └─ direct restaurant selection → restaurant reviews

search results
  ├─ select restaurant → restaurant reviews
  └─ new search → landing search

restaurant reviews
  ├─ back with saved result list → search results
  ├─ back after direct autocomplete selection → landing search
  └─ new search → landing search
```

- Preserve the query, results, pagination, selected restaurant, filters, and each surface's scroll position when moving between mobile surfaces.
- Synchronize restaurant selection with browser history using `pushState`/`popstate` or a client-side router so the iOS back gesture and browser Back action return from reviews to the correct prior surface.
- Do not send a direct autocomplete selection back to an empty result list.

The mobile restaurant screen uses a compact sticky navigation bar containing Back, the truncated restaurant name, and a Filters action. Full restaurant metadata, sync/refresh actions, topic chips, and filter fields must not all occupy one tall sticky region.

- On narrow screens, open deterministic and semantic filter controls in a full-width bottom sheet or another compact disclosure surface.
- Show the applied-filter count or state from the review screen so filters remain discoverable while the sheet is closed.
- Lay filter controls out as one column on phones, two columns on medium-width surfaces, and a horizontal toolbar only when sufficient desktop width exists.
- Render topic chips as a horizontally scrollable, non-sticky row on narrow screens; allow wrapping on wider screens.
- Keep review cards in the primary vertical scroll surface.

All frequently used mobile controls should provide an approximately 44 by 44 CSS-pixel touch target, including application chrome actions, Back, Filters, sync/refresh, topic chips, and bottom-sheet controls. Long restaurant names, addresses, reviewer names, review text, and provider URLs must wrap or truncate without increasing page width.

The developer drawer remains a right-side drawer on wide screens and becomes a safe-area-aware bottom sheet on narrow screens. Its height must use dynamic viewport sizing rather than a fixed percentage of legacy `vh`.

For Home Screen installation, add a web-app manifest with the application name, short name, start URL, standalone display mode, theme/background colors, and appropriate icons, plus an Apple touch icon and theme metadata in the document head. A service worker may cache only the versioned application shell and static assets initially; API, restaurant, review, and filtering responses remain network-driven unless an explicit cache invalidation design is added.

Respect `prefers-reduced-motion`; navigation and bottom-sheet state changes must remain understandable with transitions disabled.

#### 3.6.6 Frontend state and component plan

Use explicit view state instead of deriving layout from incidental loading flags:

```text
landing
  ├─ successful free-form search → workspace/search-results
  └─ direct restaurant selection → workspace/restaurant

workspace/search-results
  ├─ select restaurant → workspace/restaurant
  └─ new search → landing

workspace/restaurant
  ├─ select another restaurant → workspace/restaurant
  ├─ mobile back → workspace/search-results
  └─ new search → landing
```

Suggested component boundaries:

- `AppShell`
- `SearchLanding`
- `SearchPane`
- `SearchResultList`
- `RestaurantReviewPane`
- `MobileRestaurantBar`
- `MobileFilterSheet`
- `ReviewTopicChips`
- `ReviewFilters`
- `ReviewList`
- `DeveloperDrawer`
- `ProviderUsagePanel`

Keep server state in TanStack Query and layout/drawer selection state in React state. Mobile history state represents navigation only and must not become a second copy of restaurant or review server data. Enable the reviews query only when a restaurant is selected and the provider-usage query only while the developer drawer is open.

#### 3.6.7 Visual palette

Use a warm, editorial restaurant-oriented palette rather than the earlier dark green dashboard styling:

- Page background: `#F7F4EE` warm ivory
- Panes and review cards: `#FFFDFC` soft white
- Primary text: `#24313A` ink navy
- Primary accent and actions: `#B7462D` terracotta
- Map/location links and secondary location states: `#35647C` muted map blue
- Borders and dividers: `#DED8CE`
- Star ratings: `#E3A333`

Terracotta is used for primary buttons and selected restaurant accents. Muted map blue is used for map/source links, location-related states, and secondary navigational accents. Cards remain mostly soft white with subtle borders and low or no shadow.

The `Real Reviews` wordmark in the top-left application chrome acts as a home action that returns to the focused landing search state. It should not leave a persistent visual box after click; hover/focus treatment should remain subtle and not distract from the workspace.

#### 3.6.8 Accessibility and acceptance criteria

- Initial load shows a full-screen search experience with no provider-usage card.
- A successful free-form search transitions to the split workspace and focuses the results heading.
- Direct autocomplete selection transitions to the split workspace and focuses the restaurant heading.
- Selecting a result updates the right pane without clearing the result list.
- Review loading, empty, error, cached, syncing, and refreshing states remain contained in the right pane.
- The developer drawer is keyboard-operable, focus-trapped, dismissible, and absent from the normal content hierarchy while closed.
- Provider usage is not requested merely by loading the application.
- Desktop panes and mobile surface navigation preserve search and filter state.
- The iOS/browser Back action returns from restaurant reviews to saved results, or to landing after a direct autocomplete selection.
- The mobile restaurant header remains compact; topic chips and the complete filter form never consume the review viewport as one tall sticky block.
- Mobile controls meet the documented touch-target intent and remain reachable above safe-area insets.
- The application uses one shared React implementation for browser and installed Home Screen modes.
- Home Screen metadata provides the correct application name, icon, start URL, standalone display mode, theme, and background.
- Phone, landscape-phone, tablet, and desktop viewport tests show no document-level horizontal overflow.
- Layout transitions pass reduced-motion behavior and do not cause horizontal overflow.
- Frontend tests cover landing, free-form results, direct selection, result selection, drawer open/close, lazy provider query, and mobile back behavior.

#### 3.6.9 Implementation sequence

1. Extract the current search, result list, restaurant detail, filters, review list, and provider-usage markup into components without changing behavior.
2. Add the explicit landing/workspace view state and static responsive pane layout.
3. Wire free-form search and autocomplete selection to the documented transitions while preserving existing queries and mutations.
4. Move `ProviderUsagePanel` into `DeveloperDrawer` and make its query lazy.
5. Add independent desktop scrolling, sticky restaurant/filter regions, mobile search/detail navigation, and state preservation.
6. Refine mobile viewport sizing, safe areas, compact sticky navigation, filter disclosure, topic overflow, and touch targets under `BL-006`.
7. Add Home Screen manifest/icon metadata and an application-shell-only service-worker policy.
8. Add focus management, dialog semantics, history behavior, reduced-motion handling, and overflow checks.
9. Add component and responsive browser tests for the acceptance criteria before considering the mobile refinement complete.

## 4. System Architecture

### 4.1 Containers

Docker Compose will run:

- `frontend`: React, TypeScript, Vite, Tailwind CSS, TanStack Query, Google Places Autocomplete, and pnpm
- `api`: FastAPI, Pydantic, HTTPX, Uvicorn, SQLAlchemy 2, Psycopg 3, and uv
- `postgres`: persistent PostgreSQL database
- `migrate`: a short-lived Alembic migration service using the backend image

The API will use asynchronous SQLAlchemy sessions with Psycopg 3. Alembic migrations will run through the dedicated `migrate` service rather than independently inside every API process. This prevents migration races when the application later runs more than one API replica.

The Mac development host only requires Docker Desktop, Git, and an editor. Node, Python, pnpm, uv, PostgreSQL, migrations, linters, and test runners will all run in containers.

### 4.2 Provider responsibilities

#### Google Places

Google Places API (New) is responsible for:

- Place Autocomplete
- Restaurant and geographic search
- Canonical Google Place IDs
- Basic place details
- Up to five reviews only when SerpApi fails or returns no reviews

#### SerpApi

SerpApi Google Maps Reviews API is responsible for:

- Primary review retrieval
- Review pagination
- Review IDs
- Publication and edit timestamps
- Author attribution needed for display
- Restaurant-specific review topics from the initial review-page response
- Optional per-review images
- Optional dynamic `details` and `translated_details`
- Direct Google Maps review links

Only reviews whose SerpApi `source` is `Google` will be included in the first version.

The provider must read the top-level SerpApi `topics` array on the first `google_maps_reviews` page. Each topic is normalized from:

- `keyword`: display and local-filter text
- `mentions`: provider-reported mention count
- `id`: opaque provider topic ID retained verbatim

Only topic objects with non-empty `id` and `keyword` strings are accepted. Normalize `mentions` to a non-negative integer when possible and otherwise store it as null. Preserve array order as `rank`, deduplicate repeated IDs within the response, and derive `language_code` from the configured SerpApi `hl` request parameter rather than guessing it from the keyword.

Topics are fetched as part of the review request; there is no separate topic request. Later pagination pages are used for review collection only, and the implementation must not depend on those pages repeating the topic array. Google Places fallback reviews do not provide the equivalent aggregate topic list.

The separate SerpApi Google Maps Contributor Reviews API is reserved for the deferred, user-triggered reviewer-context feature in Section 17. It must never be called automatically as part of restaurant review synchronization.

#### Local LLM

The LLM is reached through an OpenAI-compatible HTTP endpoint on the Tailscale network.

The backend will support:

- Configurable base URL
- Configurable model
- Optional API key
- Request timeout
- Strict output validation
- Bounded concurrency
- Token-aware batching
- Separate prompts and request schemas for review-content filtering and reviewer-label equivalence
- Batch-local review-ID allowlists for every model response

### 4.3 Provider interfaces

Restaurant discovery and review retrieval will use separate interfaces.

```python
class RestaurantProvider(Protocol):
    async def search(self, request: RestaurantSearchRequest) -> RestaurantSearchPage:
        ...

    async def get_place(self, place_id: str) -> Place:
        ...


class ReviewProvider(Protocol):
    async def fetch_page(
        self,
        place_id: str,
        cursor: str | None,
        page_size: int,
        sort: str,
    ) -> ReviewPage:
        ...
```

`ReviewPage` will include:

```python
@dataclass
class NormalizedReviewTopic:
    provider_topic_id: str
    keyword: str
    mentions: int | None
    language_code: str | None
    rank: int


@dataclass
class ReviewPage:
    reviews: list[NormalizedReview]
    topics: list[NormalizedReviewTopic] | None
    next_cursor: str | None
    successful_request_count: int
    cached: bool
```

`topics=None` means the upstream response omitted the field. `topics=[]` means the field was present but explicitly empty. Only a non-paginated first-page response may update the stored topic snapshot.

Implementations:

- `GooglePlacesRestaurantProvider`
- `SerpApiReviewProvider`
- `GooglePlacesReviewProvider`
- `FallbackReviewProvider`

The default review configuration is SerpApi primary with Google Places fallback.

### 4.4 Package and dependency management

#### Frontend

Use pnpm with:

- `package.json` for project metadata and dependency ranges
- `pnpm-lock.yaml` committed to source control
- A pinned pnpm version declared in `package.json`
- Frozen-lockfile installation in container and CI builds
- A named Docker volume mounted at `/app/node_modules`
- A BuildKit cache or named volume for the pnpm package store

Application dependencies will be added through a container:

```bash
docker compose -f docker/compose.yaml -f docker/compose.override.yaml run --rm frontend pnpm add <package>
docker compose -f docker/compose.yaml -f docker/compose.override.yaml run --rm frontend pnpm add --save-dev <package>
```

The host workspace must never contain a frontend `node_modules` directory.

#### Backend

Use uv with:

- `pyproject.toml` for project metadata and dependencies
- `uv.lock` committed to source control
- PEP 735 dependency groups for development and test dependencies
- `uv sync --locked` for reproducible installs
- `uv run` for application, migration, lint, and test commands
- A named Docker volume mounted at `/venv` during development
- A BuildKit cache or named volume for uv's package cache

Backend dependencies will be added through a container:

```bash
docker compose -f docker/compose.yaml -f docker/compose.override.yaml run --rm api uv add <package>
docker compose -f docker/compose.yaml -f docker/compose.override.yaml run --rm api uv add --dev <package>
```

The host workspace must never contain a backend `.venv` directory.

### 4.5 Database layer

Use:

- SQLAlchemy 2 typed declarative models
- SQLAlchemy asynchronous engines and sessions in FastAPI
- Psycopg 3 as the PostgreSQL driver
- Alembic for all schema changes
- Repository and service layers so HTTP route handlers do not contain database queries directly

Migration commands will run through the dedicated service:

```bash
make migrate
docker compose -f docker/compose.yaml -f docker/compose.override.yaml run --rm migrate uv run alembic revision --autogenerate -m "describe change"
docker compose -f docker/compose.yaml -f docker/compose.override.yaml run --rm migrate uv run alembic downgrade -1
```

Generated Alembic migration files are committed to source control. PostgreSQL data remains in a named Docker volume.

### 4.6 Compose environments

Keep production-capable separation from the beginning:

```text
docker/compose.yaml
docker/compose.override.yaml
docker/compose.prod.yaml

frontend/
  Dockerfile
  package.json
  pnpm-lock.yaml

backend/
  Dockerfile
  pyproject.toml
  uv.lock
  alembic.ini
  migrations/
```

`docker/compose.yaml` is the canonical base and defines:

- Frontend, API, PostgreSQL, and migration services
- Internal networks
- Health checks
- Named data, environment, and dependency-cache volumes
- Environment-file references
- Service dependencies

`docker/compose.override.yaml` is explicitly merged by the root `Makefile` for local development and adds:

- Source-code bind mounts
- Vite and FastAPI hot reload
- Development ports
- Development image targets
- Debug logging
- Named `/app/node_modules` and `/venv` volumes

`docker/compose.prod.yaml` is explicitly selected for Oracle or production-like runs and adds:

- Immutable production image targets
- No source-code bind mounts
- No externally exposed PostgreSQL port
- Production server commands
- Restart policies
- Deployment health checks
- Host-provided secrets
- A reverse proxy when the Oracle deployment is introduced

The private Oracle/Tailscale rollout is intentionally deferred and tracked as [`BL-010`](backlog.md#bl-010--private-oracle-and-tailscale-deployment). Section 21 is authoritative for its network and operational design.

The frontend and backend Dockerfiles will use multi-stage development and production targets. Production images will contain only runtime dependencies and built application artifacts.

Validate every merged configuration with:

```bash
make config
make prod-config
```

### 4.7 Container-only development workflow

Common commands:

```bash
make up
make migrate
make api-test
make api-lint
make frontend-test
make down
```

Add `.dockerignore` and `.gitignore` rules for `node_modules`, `.venv`, caches, build output, local environment files, and editor artifacts. Dependency lockfiles and Alembic migrations are explicitly retained in source control.

## 5. API Request Flows

### 5.1 Autocomplete selection

The Google widget uses a browser-restricted key and manages its autocomplete session.

On selection, request only the minimum Place Details fields needed:

- ID
- Formatted address
- Location
- Viewport
- Types

Do not request `displayName`, `googleMapsUri`, rating, reviews, photos, opening hours, or other non-Essentials fields as part of the terminating autocomplete Place Details request. The label already supplied by the selected prediction will be used for display. A Google Maps link can be constructed from the selected Place ID or obtained later through an explicitly costed request if necessary.

This keeps the flow in the lower-cost Place Details Essentials category instead of turning the session into a Place Discovery request billed as Enterprise + Atmosphere.

As of July 28, 2026, Google classifies `googleMapsUri` as a Place Details Pro field. In an Autocomplete (New) session, requesting any Pro-or-higher Place Details field causes the terminating request to be billed as Place Details Enterprise + Atmosphere. The frontend must not request `googleMapsUri` during autocomplete termination.

The selected normalized place metadata is then submitted to FastAPI and stored. If the UI needs rating, rating count, or distance for an autocomplete-selected restaurant, it may make one explicit backend Text Search request using the selected restaurant name/address and match the returned Google Place ID. This enrichment request is intentionally separate from the autocomplete session and consumes Text Search allowance.

### 5.2 Free-form restaurant search

FastAPI calls Google Text Search (New) with a narrow field mask. Return 10 results per page by default.

When browser coordinates are provided, compute straight-line distance in the backend and sort the returned page by distance. When coordinates are not provided, preserve Google's search-result order.

The field mask may include rating and rating-count fields for search-result display. Support explicit pagination through `nextPageToken`, but never prefetch additional result pages.

Restaurant search never calls SerpApi and never retrieves reviews or review topics for the returned restaurants. Review data is requested only after the user selects one restaurant and explicitly starts synchronization.

### 5.3 Initial review synchronization

1. Check PostgreSQL for reviews associated with the selected Place ID.
2. If reviews already exist, return them together with any saved topics without calling SerpApi.
3. If none exist, call SerpApi with:
   - `engine=google_maps_reviews`
   - The Google Place ID
   - `sort_by=newestFirst`
   - `hl` set to the configured review language
4. The first request normally returns eight reviews and may include a top-level `topics` array.
5. Normalize the first-page topic array separately from the reviews. Preserve each topic ID as an opaque provider value; do not attempt to derive it from the keyword.
6. Follow pagination with up to 20 reviews per subsequent request.
7. Stop when:
   - 50 unique Google-sourced reviews have been collected,
   - pagination ends,
   - the configured request budget is reached, or
   - the user cancels the operation.
8. Persist reviews, review origins, and the topic snapshot transactionally for each successfully processed response.
9. Return reviews and topics in the synchronization response.

Retrieving 50 reviews normally requires approximately four successful SerpApi searches.

### 5.4 Load more

Implementation is tracked as [`BL-008 — Review pagination and load more`](backlog.md#bl-008--review-pagination-and-load-more). The UI and API must distinguish free PostgreSQL paging from confirmed SerpApi collection as specified in Section 19.

Before retrieving additional reviews:

1. Ask the user for or offer a target count.
2. Estimate the number of additional SerpApi searches.
3. Show the estimate and remaining locally tracked allowance.
4. Require explicit confirmation.
5. Continue pagination when the cursor remains valid.
6. If an old cursor is rejected, restart newest-first and deduplicate previously stored reviews.

### 5.5 Refresh

Reviews never refresh automatically.

A manual refresh:

1. Shows an estimated request cost.
2. Requires confirmation.
3. Starts from newest-first.
4. Reads topics from the new first-page response.
5. When the response contains a `topics` array, atomically upserts the returned topics, marks them active, and marks previously active topics for the same place/provider/language inactive when they are absent from the new snapshot. An explicit empty array therefore clears the active topic set.
6. When the upstream response omits the `topics` field entirely, do not erase the last known snapshot. Retain its fetch timestamp so the UI can distinguish saved topic data from freshly observed data.
7. Updates known reviews when edit timestamps or content changed.
8. Inserts newly discovered reviews.
9. Retains provenance for every provider response used.

The optimization to stop requesting older pages after 10 consecutive known unchanged reviews is implemented and tracked as [`BL-001`](backlog.md#bl-001--stop-refresh-pagination-after-known-unchanged-reviews).

### 5.6 Stored review filtering and sorting

Exact-rating filtering and deterministic sorting extend the existing stored-review endpoint:

```http
GET /api/v1/restaurants/{place_id}/reviews?rating=4&sort=rating_high
```

This is a PostgreSQL operation expressed through SQLAlchemy. It does not call Google, SerpApi, or the LLM. The API accepts:

- `rating`: optional integer from 1 through 5; equality filter only
- `sort`: `recent`, `oldest`, `rating_high`, or `rating_low`; defaults to `recent`

The route validates these values before they reach the repository. Do not accept arbitrary client-provided column names, sort directions, or raw SQL. Define an allowlisted enum:

```python
class ReviewSort(str, Enum):
    RECENT = "recent"
    OLDEST = "oldest"
    RATING_HIGH = "rating_high"
    RATING_LOW = "rating_low"
```

Map that enum to SQLAlchemy ordering expressions rather than SQL strings:

```python
REVIEW_SORTS = {
    ReviewSort.RECENT: (
        Review.publication_timestamp.desc().nullslast(),
        Review.id.asc(),
    ),
    ReviewSort.OLDEST: (
        Review.publication_timestamp.asc().nullslast(),
        Review.id.asc(),
    ),
    ReviewSort.RATING_HIGH: (
        Review.rating.desc().nullslast(),
        Review.publication_timestamp.desc().nullslast(),
        Review.id.asc(),
    ),
    ReviewSort.RATING_LOW: (
        Review.rating.asc().nullslast(),
        Review.publication_timestamp.desc().nullslast(),
        Review.id.asc(),
    ),
}
```

The repository starts with the selected place, applies `Review.rating == rating` only when a rating was supplied, and then applies the selected expression tuple through `order_by`. The final ID expression provides deterministic ordering when all user-visible values tie.

The service returns both the total stored-review count and the exact-filtered count. Topics remain place-level data and are not filtered or reordered by these parameters.

For the current unpaginated stored-review response, each control change may refetch from FastAPI immediately; no Apply button or debounce is required. The React Query cache key includes place ID, exact rating, and sort. When stored-review pagination is added, the same validated parameters remain authoritative in PostgreSQL and apply before limit/cursor pagination.

Basic SQL filtering runs before optional semantic filtering. Under the unified backend pipeline in Section 5.7, the frontend sends control values rather than copying stored reviews into the request. Sorting is presentation order and does not affect which reviews either LLM prompt considers.

### 5.7 Unified backend semantic filtering

Replace the current top-level `POST /api/v1/reviews/filter` contract with one restaurant-scoped backend operation:

```http
POST /api/v1/restaurants/{place_id}/reviews/filter
```

Example request:

```json
{
  "rating": 4,
  "reviewer_label": "jack",
  "content_filter": "mentions outdoor seating",
  "sort": "recent"
}
```

The fields are independently optional:

- `rating`: exact integer rating from 1 through 5
- `reviewer_label`: `null`, `jack`, `david`, or `eric`
- `content_filter`: optional bounded natural-language review-content query
- `sort`: the allowlisted sort enum from Section 5.6

The backend owns the complete filtering pipeline:

1. Load the selected restaurant and its stored reviews from PostgreSQL.
2. Apply the optional exact-rating equality filter.
3. If `reviewer_label` is not null, load only candidate review IDs and non-empty stored author display names, then run the isolated reviewer-label LLM prompt.
4. If `content_filter` is present, run the isolated review-content LLM prompt over the same SQL-filtered candidate set.
5. Parse each model response through a strict Pydantic schema containing `selected_review_ids: list[UUID]`.
6. Validate every returned UUID against the IDs in the specific batch that produced it, reject unknown or malformed IDs, and deduplicate validated results.
7. When both semantic filters are active, intersect their selected-ID sets.
8. Query PostgreSQL for the selected place and validated IDs using parameterized SQLAlchemy expressions.
9. Apply the allowlisted SQL sort.
10. Return complete review objects, counts, applied controls, and diagnostic metadata to the frontend.

The frontend does not perform the final ID intersection and does not send stored review objects back to FastAPI. It renders the `reviews` returned by this endpoint.

The reviewer-label LLM receives compact, review-boundary-preserving batches:

```json
{
  "target_label": "Jack",
  "candidates": [
    {
      "review_id": "canonical-uuid",
      "author_display_name": "stored display name"
    }
  ]
}
```

Name batching uses a model-token budget plus a maximum candidate count and never splits an individual display name. Because the payload is much smaller than review-content filtering, it has an independent conservative batch limit rather than reusing the 18,000-character review-text setting.

Both LLM prompts return the same strict shape:

```json
{
  "selected_review_ids": ["canonical-uuid"]
}
```

Do not recover IDs from prose, Markdown fences, or malformed JSON. One controlled retry may request corrected JSON; otherwise, one failed or invalid batch fails the semantic operation and leaves the deterministic SQL result visible.

After UUID validation, select results using SQLAlchemy parameters rather than string-built SQL:

```python
statement = (
    select(Review)
    .where(
        Review.place_id == place.id,
        Review.id.in_(selected_ids),
    )
    .order_by(*REVIEW_SORTS[sort])
)
```

An empty selected-ID set returns an empty result without constructing an empty `IN` clause. The maximum candidate count keeps the UUID list comfortably within PostgreSQL parameter limits; larger future datasets require pagination before semantic filtering.

Example response:

```json
{
  "reviews": [],
  "total": 50,
  "candidate_count": 12,
  "filtered_total": 4,
  "selected_review_ids": [],
  "skipped_missing_name_count": 2,
  "rating_filter": 4,
  "reviewer_label_filter": "jack",
  "content_filter": "mentions outdoor seating",
  "sort": "recent",
  "llm_used": true
}
```

`Any reviewer label` is represented as `reviewer_label: null` and skips the label LLM stage. If neither reviewer label nor content query is active, use the deterministic `GET .../reviews` path and do not call the LLM.

Reviewer-label result caching is deferred until the application has a formal `review_corpus_version` on the restaurant/place and a bounded shared cache or clearly scoped TTL/LRU. The first implementation may rerun inference on sort or repeated name-filter requests. Model decisions are not stored as durable reviewer classifications.

## 6. Persistent Data Model

### 6.1 `places`

- Internal UUID
- Google Place ID, unique
- Display name
- Formatted address
- Latitude and longitude
- Viewport
- Place types
- Google Maps URL
- Created and updated timestamps

### 6.2 `reviews`

- Canonical UUID
- Place foreign key
- Canonical author display fields
- Rating
- Review text
- Original review text, if available
- Publication timestamp
- Last edit timestamp
- Canonical source URL
- Normalized content hash
- First fetched timestamp
- Last seen timestamp

### 6.3 `review_origins`

- Canonical review foreign key
- Provider name
- Provider review ID
- Provider place ID
- Source label
- Source URL
- Contributor ID
- Author profile URL
- Author avatar URL
- Provider-supplied review image URLs
- Raw structured review details
- Raw translated structured review details
- Provider publication timestamp
- Provider edit timestamp
- Fetched timestamp

Each canonical review may have multiple origin records.

### 6.4 `review_topics`

- Internal UUID
- Place foreign key
- Provider name
- Opaque provider topic ID
- Localized keyword
- Provider-reported mention count, nullable
- Language code, nullable
- Provider display rank
- Active flag
- First seen timestamp
- Last seen timestamp
- Snapshot fetched timestamp

Use a uniqueness constraint on place, provider, provider topic ID, and normalized language code. Topic IDs must be stored as strings and treated as opaque. Add an index on place, provider, active flag, and display rank for the restaurant review response.

Topics are a place-level snapshot and are not foreign-keyed to individual reviews. Deleting a place cascades to its topics. The explicit "delete reviews" operation also deletes that place's saved topics so the next synchronization behaves like a first fetch.

### 6.5 `review_sync_runs`

- Place foreign key
- Provider
- Requested target count
- Collected unique count
- Topic field observed flag
- Topic count observed
- Successful request count
- Pagination cursor
- Status
- Error summary
- Started, updated, and completed timestamps

### 6.6 `provider_usage`

- Provider
- Plan-period identifier
- Successful request count observed by this application
- Cached response count where known
- Failed request count
- Updated timestamp

The usage table is an application-local estimate and may not include activity performed outside this application.

## 7. Deduplication

Deduplicate reviews in this order:

1. Compare SerpApi `review_id` with the suffix of Google's `places/{placeId}/reviews/{review}` resource name.
2. Extract and compare review IDs from direct Google Maps review URLs.
3. Compare an exact composite of:
   - Google Place ID
   - Contributor ID
   - Rating
   - Publication timestamp
   - Normalized-text hash
4. When contributor IDs are unavailable, compare:
   - Google Place ID
   - Normalized author name
   - Rating
   - Publication date
   - Exact normalized-text hash

Text normalization will use Unicode normalization, normalized whitespace, and stable hashing. It will not remove meaningful words or perform aggressive fuzzy matching.

Ambiguous matches remain separate and are marked as suspected duplicates. The system must prefer false negatives over incorrectly merging two different reviews.

When both providers identify the same review:

- Preserve both `review_origins` records.
- Prefer official Google fields when present.
- Use SerpApi values to fill missing canonical fields.
- Never discard provider provenance.

## 8. Backend API

### Restaurants

- `POST /api/v1/restaurants/selection`
- `GET /api/v1/restaurants/search`
- `GET /api/v1/restaurants/{place_id}`

### Reviews

- `GET /api/v1/restaurants/{place_id}/reviews`
- `POST /api/v1/restaurants/{place_id}/reviews/sync`
- `POST /api/v1/restaurants/{place_id}/reviews/refresh`
- `POST /api/v1/restaurants/{place_id}/reviews/filter`
- `DELETE /api/v1/restaurants/{place_id}/reviews`
- `GET /api/v1/reviews/filter-options`

`GET .../reviews` accepts optional `rating` and `sort` query parameters as defined in Section 5.6. The route uses a validated integer and `ReviewSort` enum and delegates filtering, ordering, and counts to the service/repository layers.

The stored-review response includes the active deterministic controls and distinguishes all stored reviews from reviews matching the exact-rating filter:

```json
{
  "reviews": [],
  "total": 50,
  "filtered_total": 12,
  "rating_filter": 4,
  "sort": "rating_high",
  "topics": [
    {
      "provider_topic_id": "/m/example",
      "keyword": "outdoor seating",
      "mentions": 24,
      "language_code": "en",
      "rank": 0
    }
  ],
  "topics_fetched_at": "2026-07-29T00:00:00Z"
}
```

`POST .../reviews/sync` and `POST .../reviews/refresh` return the newly stored review collection in the default unfiltered, most-recent order. The frontend then invalidates/refetches the parameterized `GET .../reviews` query so active deterministic controls are reapplied consistently.

The frontend must not infer review availability from the topic array. The entire filtering area is rendered only when `reviews.length > 0`. Inside that area, topic chips are optional and render only when `topics.length > 0`.

`GET /reviews/filter-options` returns the backend-controlled reviewer-label allowlist:

```json
{
  "reviewer_label_options": [
    {"value": "jack", "label": "Jack"},
    {"value": "david", "label": "David"},
    {"value": "eric", "label": "Eric"}
  ]
}
```

`POST .../reviews/filter` accepts the unified deterministic and semantic controls, performs all candidate loading, model calls, UUID validation, SQL ID filtering, sorting, and response construction described in Section 5.7. The currently implemented top-level `POST /api/v1/reviews/filter` is replaced during this work rather than maintained as a second source of filtering behavior.

### Operations

- `GET /api/v1/providers/usage`
- `GET /health`

All endpoints will use validated Pydantic request and response models. External errors will be mapped to stable application error codes without exposing credentials or upstream payloads.

The deferred reviewer-context API is specified separately in Section 17 and is not part of the v1 endpoint commitment.

## 9. Configuration and Secrets

```dotenv
VITE_GOOGLE_MAPS_BROWSER_API_KEY=
GOOGLE_MAPS_SERVER_API_KEY=
SERPAPI_API_KEY=

SERPAPI_DEFAULT_REVIEW_LIMIT=50
SERPAPI_REVIEW_SORT=newestFirst
SERPAPI_LANGUAGE=en
SERPAPI_MONTHLY_REQUEST_BUDGET=225

REVIEW_PROVIDER=serpapi
REVIEW_FALLBACK_PROVIDER=google_places

LLM_BASE_URL=
LLM_MODEL=
LLM_API_KEY=
LLM_TIMEOUT_SECONDS=60

DATABASE_URL=
FRONTEND_ORIGIN=
```

The browser Google key will be restricted by HTTP referrer and limited to the required Maps JavaScript and Places APIs.

The server Google key will be restricted to the required server-side Places APIs and, in production, the Oracle server's public IP where practical.

No credentials will be committed to source control.

## 10. Free-Tier and Cost Controls

Cross-request atomic budget reservation, idempotency, and concurrency work is tracked as [`BL-007 — Cost and concurrency protection`](backlog.md#bl-007--cost-and-concurrency-protection) and designed in Section 18.

Current global allowances as of July 2026:

| Service | Free allowance |
| --- | ---: |
| Google Autocomplete Requests | 10,000 requests per month |
| Google Autocomplete Session Usage | Unlimited |
| Google Place Details Essentials | 10,000 requests per month |
| Google Text Search Pro | 5,000 requests per month |
| Google Place Details Enterprise + Atmosphere | 1,000 requests per month |
| SerpApi Free | 250 successful searches per plan month |
| SerpApi Free throughput | 50 searches per hour |

Google requires billing to be enabled and may charge after a free allowance is exceeded.

The application will:

- Avoid non-Essentials fields during autocomplete selection.
- Never fetch Google's review field unless SerpApi fallback is needed.
- Use narrow Google field masks.
- Configure conservative Google Cloud quotas and billing alerts.
- Set the local SerpApi budget to 225 by default, leaving headroom within a 250-search plan.
- Stop new SerpApi requests when the configured limit is reached.
- Display a warning before any operation expected to use multiple searches.
- Reuse persisted reviews rather than refetching them.
- Avoid an interactive Google map in v1, preventing Dynamic Maps usage.

SerpApi counts successful, non-cached searches. Cached, failed, and errored searches do not count according to its current pricing documentation. The application will still track submitted and successful requests conservatively.

At approximately four SerpApi searches per initial 50-review fetch, the default 225-request application budget supports roughly 56 newly fetched restaurants per plan period, assuming each requires four requests.

## 11. Security, Privacy, and Compliance

- Do not log review text, author names, author profile URLs, or browser coordinates.
- Do not send author information to the review-content LLM filter. The explicit reviewer-label filter is the sole exception and may send only canonical review IDs and stored display names under the constraints in Section 5.7.
- Validate place IDs, query lengths, review counts, filter sizes, cursors, and request bodies.
- Apply request and response size limits.
- Use bounded retries only for transient upstream errors.
- Use timeouts for Google, SerpApi, and LLM requests.
- Apply CORS only to the configured frontend origin.
- Provide Google Maps attribution and direct source links.
- Preserve review author attribution required for display.
- Provide deletion controls for locally stored restaurant and review data.

SerpApi provides scraping infrastructure, not an automatic license to redistribute or commercially exploit Google review content. Persistent storage in this first version is limited to the personal research tool. A public release requires a review of Google, SerpApi, copyright, privacy, display, and downstream LLM-use requirements.

## 12. Failure Handling

### SerpApi unavailable or exhausted

- Retry transient failures within a small bounded limit.
- If SerpApi remains unavailable or returns no reviews, call Google Places for up to five reviews.
- Clearly mark fallback results.
- Do not repeatedly retry after the configured SerpApi budget is exhausted.

### Google unavailable

- Return stored place and review data when available.
- Disable new search and autocomplete-dependent operations.
- Show a clear upstream-service error without exposing credentials.

### LLM unavailable

- Continue displaying reviews.
- Preserve deterministic rating/date/text controls.
- Offer a retry action.

### Partial review synchronization

- Persist successfully normalized pages transactionally.
- Persist first-page topics with the successfully normalized first page.
- Record the run as partial.
- Allow the user to resume or restart.
- Deduplicate all restarted results.
- Do not let a later pagination failure discard an already persisted first-page topic snapshot.

## 13. Testing Plan

### Backend unit tests

- Google and SerpApi response normalization
- SerpApi topic normalization for populated, empty, and omitted topic fields
- Opaque topic ID and localized keyword preservation
- Exact-rating repository filtering, including unrated-review behavior
- Allowlisted review-sort mapping and stable null-last tie-breakers
- Provider interface compatibility
- Exact-ID deduplication
- URL-extracted-ID deduplication
- Composite deduplication
- Translated and edited reviews
- Missing authors and contributor IDs
- Same-author multiple-review cases
- Ambiguous collision handling
- LLM JSON validation and unknown-ID rejection
- Sensitive-trait filter rejection
- Reviewer-label allowlist validation and filter-options serialization for Jack, David, and Eric
- Reviewer-label prompt isolation from review text and personal-trait inference
- Reviewer-label token/count batching without splitting display names
- Reviewer-label batch-local returned-ID validation
- Usage-budget enforcement

### Integration tests

- Google Text Search with mocked pagination
- SerpApi retrieval below, at, and above 50 reviews
- Normal initial fetch completing within four SerpApi requests
- Initial review synchronization persisting topics from the first request without an extra provider call
- Refresh replacing an explicit topic snapshot while retaining the last snapshot when the field is omitted
- Stored-review endpoint validation for ratings outside 1–5 and unknown sort values
- Exact-rating and each deterministic sort mode against PostgreSQL
- Correct `total` and `filtered_total` counts
- Basic SQL filtering occurring before optional LLM filtering
- Unified restaurant-scoped filter endpoint for deterministic-only, label-only, content-only, and combined filtering
- Reviewer-label candidate loading using only review ID and non-empty author display name
- Reviewer-label filtering respecting the optional exact-rating candidate filter
- Missing reviewer labels reported as skipped without being sent to the LLM
- Multi-batch reviewer-label result merging and all-or-nothing failure behavior
- Strict UUID response parsing, batch-local allowlists, parameterized SQL ID filtering, and empty-ID behavior
- Invalid and expired pagination tokens
- Empty SerpApi results and Google fallback
- Partial synchronization recovery
- Manual refresh
- Database persistence across restarts
- Explicit review deletion

### Frontend tests

- Geolocation permission granted, denied, unavailable, and timed out
- Autocomplete keyboard and mobile interaction
- Restaurant selection
- City or neighborhood selection
- Free-form search without a selected suggestion
- Review fetch progress and cancellation
- First-time restaurant state hiding topics and filter controls before reviews exist
- Saved restaurant state loading reviews and topics without an upstream request
- Restaurant-specific topic rendering with no hard-coded fallback topics
- Reviews-without-topics state retaining free-form and rating filters
- Topic click populating the local filter without a SerpApi request
- Exact 1–5-star filtering without minimum-rating behavior
- Most-recent, oldest, highest-rated, and lowest-rated ordering
- Null-rating and null-date placement, stable ties, and result-count display
- Rating changes clearing stale semantic IDs while sort changes preserve them
- Review-query cache keys including place, rating, and sort
- Always-visible reviewer-label dropdown with Any, Jack, David, and Eric
- Any reviewer label skipping label-related LLM inference
- Reviewer-label and review-content controls operating independently
- Combined label/content results returned by the backend while preserving exact rating and SQL sort
- Topic-chip selection preserving the reviewer-label dropdown value
- Review refresh invalidating cached semantic results while sort-only changes reuse them
- Load-more cost confirmation
- Usage-limit messaging
- LLM filtering and fallback
- Google attribution visibility
- Responsive layouts and accessibility
- Mobile list/detail navigation at 390×844, including Back/popstate behavior and preserved result/filter state
- Landscape-phone layout at 844×390 without clipped or unreachable controls
- Tablet layout at 768×1024 and desktop split layout at 1280×800
- No document-level horizontal overflow at the supported responsive viewports
- Dynamic viewport-height and safe-area behavior in browser and standalone display modes
- Compact mobile restaurant navigation with non-sticky topic/filter content
- One-column phone, two-column medium, and wide-screen filter layouts
- Home Screen manifest metadata, icons, standalone start URL, and application-shell cache policy
- Minimum mobile touch-target intent for primary navigation and actions

### Container verification

- `make up`
- `make config`
- Production Compose configuration validation
- Health checks
- Frontend-to-API connectivity
- API-to-PostgreSQL connectivity
- API-container access to the Tailscale LLM endpoint
- pnpm frozen-lockfile installation
- uv locked dependency synchronization
- Named `node_modules` and `.venv` volume behavior
- Migration from an empty database
- Migration upgrade and one-step downgrade
- Restart with persisted database volume

## 14. Initial Delivery Order

1. Scaffold the base, development, and production Compose files plus multi-stage frontend and backend Dockerfiles.
2. Initialize the frontend with pnpm and the backend with uv; commit both lockfiles.
3. Add PostgreSQL, SQLAlchemy 2, Psycopg 3, Alembic, and the dedicated migration service.
4. Add configuration validation, health checks, and container-only development commands.
5. Integrate Google Places Autocomplete with minimal fields and location bias.
6. Add Google Text Search and selected-place persistence.
7. Add SerpApi review pagination with a configurable 50-review target.
8. Add normalization, PostgreSQL models, migrations, and deduplication.
9. Add usage tracking, fetch progress, cancellation, and cost confirmations.
10. Add Google Places review fallback.
11. Add the OpenAI-compatible LLM filter adapter and token-bounded batching.
12. Complete responsive UI, attribution, error states, and accessibility.
13. Add automated tests and verify both development and production-like container configurations.

## 15. Initial Assumptions

- The first audience is one personal user.
- The application runs locally on the Mac during development.
- The Mac only needs Docker Desktop, Git, and an editor; project runtimes and dependencies stay in containers.
- pnpm is the frontend package manager and `pnpm-lock.yaml` is authoritative.
- uv is the backend package manager and `uv.lock` is authoritative.
- SQLAlchemy 2, Psycopg 3, and Alembic form the database layer.
- Compose uses a canonical base plus development and production overrides from the beginning.
- The home Linux LLM is accessible through Tailscale.
- The LLM implements an OpenAI-compatible chat-completions interface.
- Oracle deployment is deferred, but container and configuration boundaries will remain deployment-ready.
- Stored reviews are snapshots and never refresh automatically.
- The initial SerpApi target is 50 reviews and is configurable.
- SerpApi is primary; Google Places reviews are fallback only.
- No interactive map is included in v1.
- No authentication is required while v1 is accessible only on the developer's trusted local/Tailscale network. Any internet-accessible Oracle deployment requires authentication or another explicit access-control boundary before release.

## 16. Implementation Snapshot

The initial project scaffold has been created according to the delivery order and container-only workflow.

### 16.1 Repository structure and environment

Implemented root project files:

- `README.md` with first-run and container-only workflow commands.
- `.env.example` containing all frontend, backend, provider, database, LLM, and cost-control configuration keys.
- `.gitignore` excluding local secrets, host dependency folders, caches, build output, and editor artifacts.
- `docker/compose.yaml` as the canonical base Compose file.
- `docker/compose.override.yaml` for local development hot reload, development ports, and named dependency volumes.
- `docker/compose.prod.yaml` for production-like image targets and runtime commands.
- Root `Makefile` wrapping the standard Docker Compose commands, including `make up`, `make down`, and `make down-volumes`.

The development workflow keeps runtime dependencies inside containers and named Docker volumes rather than host `node_modules` or `.venv` directories.

### 16.2 Docker and dependency management

Implemented frontend containerization:

- `frontend/Dockerfile` with multi-stage `development`, `build`, and `production` targets.
- `frontend/.dockerignore` to exclude local dependency/cache/build artifacts.
- `frontend/nginx.conf` for production static serving.
- `frontend/package.json` using pinned `pnpm@9.15.4`.
- `frontend/pnpm-lock.yaml` committed for reproducible frontend installs.

Implemented backend containerization:

- `backend/Dockerfile` with multi-stage `development` and `production` targets.
- `backend/.dockerignore` to exclude local virtualenv/cache artifacts.
- `backend/pyproject.toml` using uv-managed dependencies and dependency groups.
- `backend/uv.lock` committed for reproducible backend installs.
- Backend virtualenv path configured as `/venv` in containers so host `backend/.venv` is not created during bind-mounted development.

### 16.3 Backend application scaffold

Implemented a FastAPI backend with:

- Application entrypoint: `backend/app/main.py`.
- API router registration: `backend/app/api/router.py`.
- Route modules under `backend/app/api/routes/`.
- Pydantic settings validation: `backend/app/core/config.py`.
- Stable application error helper: `backend/app/core/errors.py`.
- Async SQLAlchemy engine/session setup: `backend/app/db/session.py`.
- Shared declarative base and timestamp/UUID helpers: `backend/app/db/base.py`.

Initial API routes implemented:

- `GET /health`
- `GET /api/v1/health`
- `POST /api/v1/restaurants/selection`
- `GET /api/v1/restaurants/search`
- `GET /api/v1/restaurants/{place_id}`
- `GET /api/v1/restaurants/{place_id}/reviews`
- `POST /api/v1/restaurants/{place_id}/reviews/sync`
- `POST /api/v1/restaurants/{place_id}/reviews/refresh`
- `DELETE /api/v1/restaurants/{place_id}/reviews`
- `POST /api/v1/reviews/filter`
- `GET /api/v1/providers/usage`

### 16.4 Database and migrations

Implemented SQLAlchemy 2 models:

- `backend/app/models/place.py`
- `backend/app/models/review.py`
- `backend/app/models/review_origin.py`
- `backend/app/models/review_sync_run.py`
- `backend/app/models/provider_usage.py`

Implemented Alembic setup:

- `backend/alembic.ini`
- `backend/migrations/env.py`
- `backend/migrations/script.py.mako`
- `backend/migrations/versions/0001_initial.py`

The initial migration creates:

- `places`
- `reviews`
- `review_origins`
- `review_sync_runs`
- `provider_usage`

### 16.5 Backend provider, repository, and service layers

Implemented provider interfaces and provider adapters:

- `backend/app/providers/base.py`
- `backend/app/providers/google_places.py`
- `backend/app/providers/serpapi.py`
- `backend/app/providers/fallback.py`

Implemented repositories:

- `backend/app/repositories/places.py`
- `backend/app/repositories/reviews.py`
- `backend/app/repositories/usage.py`

Implemented services:

- `backend/app/services/restaurants.py`
- `backend/app/services/reviews.py`
- `backend/app/services/filtering.py`

Implemented utility modules:

- `backend/app/utils/text.py` for Unicode/whitespace normalization and stable hashing.
- `backend/app/utils/dates.py` for best-effort upstream timestamp parsing.

Implemented API schemas:

- `backend/app/schemas/common.py`
- `backend/app/schemas/restaurants.py`
- `backend/app/schemas/reviews.py`
- `backend/app/schemas/operations.py`

### 16.6 Review retrieval and filtering behavior implemented

The backend now supports:

- Selected-place persistence from frontend Google Autocomplete metadata.
- Google Text Search using Places API (New) with a narrow field mask.
- Stored review listing per Google Place ID.
- SerpApi review synchronization with configurable target count and sort order.
- Local SerpApi usage tracking.
- Cost confirmation before multi-request review sync operations.
- Google Places review fallback when the primary review provider fails before any review is stored or returns an initially empty result set.
- Normalized review persistence with canonical review and origin/provenance records.
- Basic deduplication by provider review ID across providers, URL-extracted Google review IDs, contributor-aware composite matching, and place/rating/publication-timestamp/content-hash matching.
- Manual review deletion per place.
- OpenAI-compatible LLM review filtering that sends only review ID, text, rating, and publication date.
- Sensitive-trait filter rejection in the request schema.
- Strict JSON parsing and unknown-review-ID rejection for LLM responses.

### 16.7 Frontend application scaffold

Implemented a responsive React/Vite/Tailwind frontend with:

- Entry files: `frontend/src/main.tsx`, `frontend/src/App.tsx`, and `frontend/src/styles.css`.
- API client: `frontend/src/lib/api.ts`.
- Google Maps script loader: `frontend/src/lib/googleMaps.ts`.
- Google Places Autocomplete component: `frontend/src/components/Autocomplete.tsx`.
- Shared API types: `frontend/src/types/api.ts`.
- Google Places TypeScript augmentation: `frontend/src/types/google-places.d.ts`.
- Vite environment typing: `frontend/src/vite-env.d.ts`.

Frontend behavior implemented:

- Google Places `PlaceAutocompleteElement` loading.
- Immediate browser geolocation request with coordinates kept only in browser memory.
- 5 mile autocomplete location bias when geolocation succeeds.
- IP-based Google bias fallback when geolocation is denied, unavailable, or times out.
- Essentials-only selected-place field fetch: ID, formatted address, location, viewport, and types. Google Maps links are synthesized from the Place ID instead of requesting the Pro `googleMapsUri` field during autocomplete termination.
- Free-form restaurant search against the backend with 10 results per page, rating, review count, distance in miles when available, and explicit next-page loading.
- Search-result selection and persistence.
- Restaurant detail panel with Google Maps link, rating, review count, and distance when available from search enrichment.
- Direct autocomplete selections remain Essentials-only and then perform one explicit backend Text Search enrichment request to match rating/distance metadata by Place ID.
- Review sync button with backend cost-confirmation handling.
- Provider usage moved to a lazy developer drawer opened by a gear icon.
- Topic chips, natural-language LLM review filter field, and deterministic minimum-rating filter.
- Review list display with rating, date, author attribution when available, source labels, text, and original source link.

### 16.8 Verification completed

The following checks were run successfully:

- `make config`
- `make prod-config`
- Backend image build for `api` and `migrate`.
- Frontend production build through the Docker `build` target.
- `docker run --rm real-reviews-api uv run ruff check .`
- `docker compose -f docker/compose.yaml -f docker/compose.override.yaml up -d api` followed by `GET /health` returning database `ok`.
- `docker compose -f docker/compose.yaml -f docker/compose.override.yaml up -d frontend` followed by successful HTTP response from `http://localhost:5173`.
- A smoke test for `POST /api/v1/restaurants/selection` and `GET /api/v1/restaurants/{place_id}/reviews`.

### 16.9 Follow-up implementation from audit feedback

After the July 28, 2026 source-level audit, the following corrective changes were made.

#### 16.9.1 Cost and production-path fixes

- Removed the Pro-class `googleMapsURI` field from frontend autocomplete termination. The frontend now requests only ID, formatted address, location, viewport, and types, then synthesizes a Google Maps link from the Place ID.
- Changed the frontend API fallback from `http://localhost:8000/api/v1` to relative `/api/v1`, so production bundles can call through same-origin Nginx.
- Updated `frontend/nginx.conf` to proxy `/api/` and `/health` to the internal FastAPI service at `api:8000`.
- Added separate development and production image tags:
  - `real-reviews-api-dev` / `real-reviews-api-prod`
  - `real-reviews-migrate-dev` / `real-reviews-migrate-prod`
  - `real-reviews-frontend-dev` / `real-reviews-frontend-prod`
- Added a production frontend health check.
- Updated production Compose environment overrides so production-like runs rely on explicitly supplied environment values instead of the development defaults.

#### 16.9.2 Review synchronization and provider fixes

- Corrected SerpApi request estimation for the documented first-page shape: a 50-review target now estimates four searches rather than three.
- Added `cursor` to `ReviewSyncRequest` so callers can resume from an explicit pagination cursor.
- Changed sync loop accounting so refresh/forced sync stops based on processed provider reviews rather than only newly created canonical rows.
- Added per-page commits during sync so successfully normalized pages survive later page failures.
- Added provider selection through `REVIEW_PROVIDER` and `REVIEW_FALLBACK_PROVIDER` for the supported `serpapi` and `google_places` providers.
- Added fallback when the primary provider returns an initially empty review page, not only when it raises an exception.
- Added failed-provider usage increments for provider request failures.
- Added stable `UPSTREAM_ERROR` mapping for HTTPX upstream failures.
- Added a PostgreSQL advisory per-place sync lock to prevent duplicate concurrent syncs for the same place.

#### 16.9.3 Deduplication and persistence fixes

- Added `backend/app/utils/review_ids.py` for Google review ID extraction from resource names and review URLs.
- Expanded deduplication to check provider review IDs across providers, not only within the same provider.
- Added contributor-ID-aware composite matching before falling back to place/rating/publication-timestamp/content-hash matching.
- Added normalized-author fallback when multiple composite matches exist.
- Added Google canonical-field precedence: official Google values overwrite canonical fields, while non-Google provider values fill missing fields when Google data already exists.
- Added migration `0002_relax_review_uniqueness.py` and updated the model to remove the overly aggressive `(place_id, normalized_content_hash, rating)` unique constraint.
- Changed sync response `collected_unique_count` to report newly collected canonical rows for the current run rather than total stored rows.

#### 16.9.4 LLM filtering fixes

- Raised the filter request limit from 200 to 500 reviews to match the maximum review-sync target.
- Implemented bounded concurrent LLM batch execution using `LLM_MAX_CONCURRENCY`.
- Added deterministic minimum-rating filtering in the frontend.
- Changed LLM filter failure handling to clear previous LLM selections and restore the unfiltered deterministic result set.
- Added an initial backend test covering sensitive-trait request rejection.

#### 16.9.5 Frontend flow and attribution fixes

- Added a frontend next-page action for free-form Google Text Search results when the backend returns `next_page_token`.
- Added visible review author display when author attribution is present.
- Added a small deterministic frontend review-filter helper and unit test.

#### 16.9.6 Testing and CI fixes

- Added backend tests:
  - `backend/tests/test_text_utils.py`
  - `backend/tests/test_review_filter_schema.py`
- Added frontend test:
  - `frontend/src/lib/reviews.test.ts`
- Added GitHub Actions workflow `.github/workflows/ci.yaml` to validate Compose config, build development images, run backend Ruff, run backend Pytest, build the frontend production target, and run frontend Vitest.
- Updated settings parsing so empty optional environment values, such as an unset `LLM_BASE_URL`, are treated as absent instead of failing startup validation.

#### 16.9.7 Frontend workspace and visual polish

- Implemented the Section 3.6 search-to-reviews split workspace.
- Extracted the previous large `App.tsx` into focused components and shared UI types.
- Added the warm ivory, soft white, ink navy, terracotta, muted map blue, border, and star-rating palette from Section 3.6.7.
- Changed the developer trigger from visible `Developer` text to an accessible gear icon.
- Made the top-left `Real Reviews` wordmark a home action that returns to the landing search state without leaving a persistent focus box.
- Added free-form search result metadata display for rating, review count, and distance in miles.
- Added the same rating/review-count/distance metadata to the selected restaurant review header when available.
- Added one explicit Text Search enrichment request after direct autocomplete selection so autocomplete-selected restaurants can show rating and distance metadata while keeping the terminating autocomplete Place Details request Essentials-only.
- Added frontend tests covering landing, free-form transition, direct autocomplete transition, result switching, developer drawer lazy fetching, and mobile back navigation.
- Added reduced-motion CSS handling and developer-drawer focus trapping.

#### 16.9.8 Review topics and Docker workflow updates

- Added SerpApi first-page review-topic extraction and normalization.
- Added `review_topics` persistence and migration `0004_add_review_topics.py`.
- Added topics and `topics_fetched_at` to review list and sync responses.
- Removed hard-coded frontend topic chips; topics now render only from saved restaurant-specific provider data and only after reviews exist.
- Topic chips are labeled `Mentioned in reviews`; clicking a chip applies that topic through the existing local/LLM review filter without making a SerpApi topic request.
- Added `SERPAPI_LANGUAGE` configuration support so topic language metadata follows the configured SerpApi `hl` parameter.
- Moved Compose files into `docker/` and adjusted build contexts, env-file paths, and development bind mounts.
- Added the root `Makefile` for common Docker commands including `make up`, `make down`, `make down-volumes`, validation, builds, migrations, lint, and tests.

#### 16.9.9 Exact-star filtering and deterministic review sorting

- Added validated `rating` and `sort` query parameters to `GET /api/v1/restaurants/{place_id}/reviews`.
- Added the backend `ReviewSort` allowlist with `recent`, `oldest`, `rating_high`, and `rating_low` values.
- Mapped sort values to SQLAlchemy expressions with null-last behavior and review-ID tie breakers rather than client-provided SQL or column names.
- Added exact-rating repository filtering; selecting 4 stars means `Review.rating == 4`, not 4 stars and above.
- Added stored-review `total` and `filtered_total` counts while keeping topics place-level and independent of filtering/sorting.
- Updated frontend review query keys to include place ID, exact rating, and sort.
- Replaced the previous minimum-rating selector with exact star choices and added deterministic sort controls.
- Added immediate refetch behavior, reset controls, `filtered_total of total reviews` feedback, and empty states for no exact-rating matches.
- Rating changes clear active semantic selections; sort-only changes preserve semantic membership.
- Restaurant changes reset rating, sort, and semantic state.
- Added backend sort allowlist/tie-breaker tests and frontend deterministic-control tests.

#### 16.9.10 Unified backend semantic filtering and reviewer-label dropdown

- Removed the old top-level `POST /api/v1/reviews/filter` endpoint and frontend client path.
- Added `GET /api/v1/reviews/filter-options` with backend-owned reviewer-label options for Jack, David, and Eric.
- Added `POST /api/v1/restaurants/{place_id}/reviews/filter` for unified deterministic, reviewer-label, and content filtering.
- Added validated backend request/response schemas for exact rating, reviewer-label key, content filter, allowlisted sort, full review results, counts, selected IDs, skipped missing-label count, applied controls, topics, and `llm_used`.
- Added isolated reviewer-label LLM batching that sends only target label, review ID, and stored author display name.
- Added conservative label-equivalence prompting: Jack does not match Jackie/Jackson/Jacqueline/John; Dave may match David; Erik may match Eric; uncertain entries are excluded.
- Added isolated content LLM batching that sends only review ID, text, rating, and publication date.
- Added strict JSON/Pydantic parsing, one controlled JSON retry, per-batch UUID validation, deduplication, and intersection for combined label/content filters.
- Added place-constrained SQLAlchemy ID loading and empty-selected-ID handling without constructing an empty `IN` clause.
- Updated the frontend to render backend filter responses directly rather than performing final selected-ID intersection.
- Added the reviewer-label dropdown beside rating and sort, populated from the backend options endpoint.
- Preserved immediate topic-chip filtering via the unified endpoint with current rating, reviewer label, and sort controls.
- Added inline failure messaging that preserves the previous or deterministic review results when semantic filtering fails.
- Deferred reviewer-label caching until a formal review-corpus version and shared/bounded cache are introduced.
- Added backend payload-isolation/UUID-validation tests and frontend reviewer-dropdown/failure-preservation tests.

#### 16.9.11 Mobile-first responsive web app and Home Screen experience

- Added Playwright browser testing with Chromium responsive projects for 390×844, 844×390, 768×1024, and 1280×800, plus a smaller WebKit mobile smoke suite.
- Added a Docker Compose `e2e` profile/service using the Playwright browser image so browser dependencies stay out of the production frontend image.
- Added dynamic viewport and safe-area CSS primitives, mobile scroll ownership, overscroll containment, horizontal-overflow protection, and mobile touch-target normalization.
- Added browser-history-aware mobile navigation so result-selected restaurants can return to preserved results, while direct selections return to landing.
- Added a compact mobile restaurant bar and safe-area-aware mobile filter bottom sheet while retaining the desktop inline filter toolbar.
- Moved topic chips into a non-sticky shared topic row that scrolls horizontally on phones and wraps on wider layouts.
- Added installable Home Screen metadata, `manifest.webmanifest`, theme metadata, SVG manifest icon, and Apple touch icon without adding a service worker.
- Added `make frontend-e2e` for the Playwright suite and kept Vitest/jsdom for component/state coverage.

### 16.10 Remaining known work

The following items remain open after the follow-up implementation:

- Reviewer-label filter caching using a formal `review_corpus_version` plus a bounded shared cache or clearly scoped TTL/LRU.
- [`BL-009`](backlog.md#bl-009--rich-review-data): SerpApi review-image, `details`, and `translated_details` persistence, API exposure, and review-card rendering.
- [`BL-010`](backlog.md#bl-010--private-oracle-and-tailscale-deployment): private Oracle/Tailscale ingress, TLS, access control, backups, and operations.
- A stronger production secret-delivery mechanism beyond environment variables and local `.env` conventions.
- [`BL-007`](backlog.md#bl-007--cost-and-concurrency-protection): global atomic SerpApi budget reservation, idempotency keys, and concurrency limits.
- Progress streaming, job state endpoints, and cancellation controls.
- [`BL-008`](backlog.md#bl-008--review-pagination-and-load-more): stored-review pagination, load-more UI, target selection, and provider-cursor resume.
- Full suspected-duplicate marking for ambiguous deduplication cases.
- Stored-review pagination and response-size controls.
- Token-aware LLM batching using an actual tokenizer rather than character-count sizing.
- Date filtering controls and deterministic text-search fallback.
- Broader LLM safety tests for bypasses, false positives, and prompt injection in review text.
- Autocomplete routing by place type for geographic selections and unrelated establishments.
- Restaurant detail endpoint usage in the UI, including stored count and last fetch time.
- Persistent fallback status in restaurant detail views.
- Automated accessibility coverage for error, empty, loading, keyboard, and mobile states.
- Broader backend, integration, contract, provider-fixture, deduplication, cost-control, and frontend-flow tests.
- Structured request logging/request IDs, metrics, alerting, backup/restore documentation, and secret-rotation documentation.
- Controlled live-provider smoke-test procedure using real credentials and explicit allowance-awareness.

### 16.11 Verification after follow-up changes

The follow-up implementation was verified with:

- `make config`
- `make prod-config` with production environment variables supplied.
- Development backend/frontend/migration image builds.
- Production backend/frontend/migration image builds.
- `docker run --rm real-reviews-api-dev uv run ruff check .`
- `docker run --rm real-reviews-api-dev uv run pytest`
- `docker run --rm real-reviews-frontend-dev pnpm test`
- Frontend production Docker `build` target.
- `docker compose -f docker/compose.yaml -f docker/compose.override.yaml up -d api` followed by `GET /health` returning database `ok` from a fresh PostgreSQL volume.
- `docker compose -f docker/compose.yaml -f docker/compose.override.yaml up -d frontend` followed by a successful HTTP response from `http://localhost:5173`.

## 17. Deferred Feature: On-Demand Reviewer Context

Reviewer context is a future, explicitly user-triggered feature. It may summarize a reviewer's public Google Maps contribution history as additional context, but it will not label a review as true, false, good, bad, credible, or untrustworthy.

Backlog tracking: [`BL-002 — On-demand reviewer context and rating baseline`](backlog.md#bl-002--on-demand-reviewer-context-and-rating-baseline). The backlog status is authoritative; this section is the supporting design.

### 17.1 User interaction

When a SerpApi review origin contains a contributor ID, the review card may show an action such as:

```text
Load reviewer context — may use 1 SerpApi search
```

The action must:

1. Appear only when a usable public contributor ID exists.
2. Never prefetch contributor history on hover, page load, review sync, or background refresh.
3. Check for an existing permitted context snapshot before making an upstream request.
4. Clearly disclose whether a live fetch will consume a SerpApi search.
5. Require explicit confirmation before the first paid/live lookup when no reusable snapshot exists.
6. Open a drawer or modal without navigating away from the restaurant.
7. Fall back to the contributor's Google Maps profile link when enrichment is unavailable.

After context is available, the action may read `Reviewer context` without a cost warning until the snapshot expires or is deleted.

### 17.2 Provider flow

The backend will use the contributor ID from the existing SerpApi review origin to call:

```text
engine=google_maps_contributor_reviews
contributor_id=<public Google Maps contributor ID>
hl=en
num=200
```

SerpApi currently limits contributor results to a maximum of 200 public reviews. One contributor lookup is a separate SerpApi search from the restaurant-review searches.

Proposed endpoints:

- `GET /api/v1/reviews/{review_id}/reviewer-context` returns an existing context snapshot without triggering an upstream request.
- `POST /api/v1/reviews/{review_id}/reviewer-context` explicitly requests enrichment and accepts cost confirmation.
- `DELETE /api/v1/reviews/{review_id}/reviewer-context` deletes locally retained context for that contributor, subject to shared-reference handling.

The POST operation must be concurrency-safe and idempotent per contributor so simultaneous clicks do not create duplicate upstream searches.

### 17.3 Context shown

The initial drawer may show:

- Public display name, avatar, profile link, and Local Guide status
- Public contribution counts supplied by SerpApi
- Number of public reviews actually observed in the returned sample
- Overall observed average rating
- Observed restaurant-review count
- Observed counts and average ratings by normalized restaurant category
- The current review's difference from the reviewer's observed overall and category averages
- A small, clearly labeled sample of relevant public reviews with direct Google Maps links

Category experience is context, not a verdict. No observed category history must be shown as `No public category history observed`, not as zero expertise or a negative score. A first review in a category must not be demoted merely because prior public reviews are unavailable.

### 17.4 Derived signals

Prefer transparent deterministic calculations over an LLM-generated credibility score:

```text
overall_average = mean(observed public ratings)
category_average = mean(observed ratings for normalized matching categories)
overall_rating_difference = current_rating - overall_average
category_rating_difference = current_rating - category_average
category_sample_size = count(observed matching-category reviews)
```

Any confidence indicator must be based on disclosed sample size and Bayesian/shrinkage logic so one or two category reviews do not appear conclusive. Local Guide status, contribution points, review count, text length, structured details, and photos may be displayed as separate signals but must not independently determine trustworthiness.

Restaurant categories may be derived from SerpApi contributor-review `place_info.type` and normalized through a documented mapping. Ambiguous category matches must remain broad rather than being forced into a narrow cuisine.

### 17.5 Data minimization and safety

- Use only public contributor data returned for the selected review.
- Do not infer race, ethnicity, nationality, religion, gender, age, disability, politics, home location, or other sensitive/personal traits.
- Do not use reviewer labels, avatars, addresses, or travel patterns for scoring.
- Do not send contributor profiles or full review histories to the LLM.
- Prefer retaining derived aggregate statistics and source identifiers over full copied histories.
- Avoid retaining exact coordinates or addresses when category-level aggregates are sufficient.
- Give context snapshots a documented retention/refresh policy consistent with Google and SerpApi terms.
- Provide deletion and handle a contributor shared by reviews from multiple stored restaurants.
- Keep this feature disabled for any public release until privacy, retention, attribution, and provider terms have been reviewed.

### 17.6 Cost controls

Automatically enriching 50 unique reviewers could add up to 50 SerpApi searches to the approximately four searches used for an initial 50-review restaurant fetch. Therefore:

- Reviewer-context searches have a separate local usage category, such as `serpapi_contributor_reviews`.
- They count against the same configured global SerpApi allowance unless the account reports otherwise.
- The UI displays the remaining locally tracked allowance before a live lookup.
- The backend enforces the global atomic budget reservation planned in Section 18 and tracked as BL-007.
- Context is fetched only on explicit click; bulk enrichment is out of scope.

## 18. Planned Feature: Cost and Concurrency Protection

Backlog tracking: [`BL-007 — Cost and concurrency protection`](backlog.md#bl-007--cost-and-concurrency-protection). The backlog status is authoritative.

### 18.1 Existing protection and remaining gap

The current application already has:

- A PostgreSQL advisory lock that prevents two active review synchronizations for the same Google Place ID
- Locally persisted successful, cached, and failed provider-usage counters
- Cost confirmation before operations estimated to require multiple SerpApi searches
- Disabled sync/refresh buttons while the current browser mutation is pending
- Bounded LLM batch concurrency

Those controls do not prevent two different restaurants from simultaneously observing the same remaining SerpApi balance and both spending it. Browser retries also lack a durable operation identity. BL-007 adds an atomic reservation boundary shared by every paid SerpApi operation.

### 18.2 Budget-reservation model

Add a PostgreSQL-backed reservation record such as:

```text
provider_budget_reservations
- id
- provider
- plan_period
- operation_type
- place_id nullable
- idempotency_key
- requested_units
- settled_successful_units
- settled_cached_units
- settled_failed_units
- status: reserved | running | completed | failed | expired
- lease_expires_at
- created_at
- updated_at
- completed_at nullable
```

The provider/plan-period/idempotency-key tuple is unique. A companion period-summary row may cache totals, but correctness must come from one transactional PostgreSQL operation rather than an in-memory read-then-write sequence.

Reservation algorithm:

1. Validate the operation and calculate its conservative maximum search count.
2. Acquire the operation's per-place advisory lock when it mutates restaurant reviews.
3. Begin a short database transaction.
4. Lock the provider/period budget row or execute one conditional atomic update.
5. Calculate `settled successful + active reserved + requested`.
6. Reject with `PROVIDER_BUDGET_EXHAUSTED` when it would exceed the configured local limit.
7. Insert the reservation and commit before making an upstream request.
8. Mark the reservation running and heartbeat only between provider requests.
9. Settle actual successful/cached/failed counts after every completed provider response.
10. Release unused reserved units when the operation ends.

No database transaction remains open during HTTP or LLM calls.

### 18.3 Idempotency

Paid mutations accept an `Idempotency-Key` header generated once for a user action:

- Review sync
- Refresh
- Fetch older reviews
- Future reviewer-context enrichment

Repeating the same key with the same operation parameters returns the existing running or completed operation. Reusing it with different parameters returns `IDEMPOTENCY_CONFLICT`. The key is not derived solely from the restaurant because the user must be able to intentionally run a later refresh.

The frontend retains a key across confirmation and network retry, then creates a new key for a new explicit click.

### 18.4 Concurrency limits

Keep separate limits for:

- One active review mutation per restaurant through the existing advisory lock
- Global SerpApi request concurrency, initially a small configurable process-local semaphore
- Local LLM concurrency through `LLM_MAX_CONCURRENCY`
- Optional provider-period and rolling-hour request ceilings

The initial Oracle deployment uses one API replica. Horizontal API scaling is prohibited until the SerpApi concurrency lease is shared across replicas. Atomic budget reservation remains cross-process safe regardless.

### 18.5 Operation response and UI

Provider mutations return or expose:

```json
{
  "operation_id": "uuid",
  "status": "completed",
  "estimated_request_count": 2,
  "successful_request_count": 2,
  "cached_response_count": 0,
  "failed_request_count": 0,
  "released_reserved_count": 0,
  "remaining_local_budget": 211,
  "stop_reason": "known_unchanged_streak"
}
```

The restaurant pane shows pending, success, and failure feedback. The developer drawer may expose reservations and uncertain outcomes, but it must not expose API keys or raw provider payloads.

Stable errors include:

- `COST_CONFIRMATION_REQUIRED`
- `PROVIDER_BUDGET_EXHAUSTED`
- `PROVIDER_HOURLY_LIMIT_REACHED`
- `SYNC_ALREADY_RUNNING`
- `IDEMPOTENCY_CONFLICT`

### 18.6 Recovery and tests

- A reservation has a lease long enough for the bounded operation timeout.
- A crashed reservation becomes reclaimable only after lease expiration.
- Settlement is monotonic and never reduces already observed successful usage.
- An uncertain provider outcome is counted conservatively until reconciled.
- Database, API, and race tests run two independent transactions to prove the final budget unit cannot be double-reserved.
- Tests also cover duplicate keys, parameter conflicts, same-place locking, different-place contention, cancellation, crashes, and unused-unit release.

## 19. Planned Feature: Review Pagination and Load More

Backlog tracking: [`BL-008 — Review pagination and load more`](backlog.md#bl-008--review-pagination-and-load-more). The backlog status is authoritative.

### 19.1 Separate local browsing from provider collection

Two operations must not share the same ambiguous `Load more` label:

```text
Show more saved reviews
  PostgreSQL only; no provider cost

Fetch older reviews
  SerpApi collection; estimated cost and confirmation required
```

Infinite scrolling may be used only for already stored pages. It must never trigger paid provider collection.

### 19.2 Stored-review API

Extend the deterministic endpoint:

```http
GET /api/v1/restaurants/{place_id}/reviews
    ?rating=4
    &sort=recent
    &page_size=20
    &cursor=<opaque cursor>
```

Response:

```json
{
  "reviews": [],
  "page_size": 20,
  "next_cursor": "opaque-or-null",
  "has_more": true,
  "total": 180,
  "filtered_total": 42,
  "rating_filter": 4,
  "sort": "recent",
  "topics": [],
  "topics_fetched_at": null
}
```

Use keyset pagination, not offset pagination. Each cursor binds:

- Google Place ID
- Exact-rating filter
- Allowlisted sort
- Last row's ordered values and review ID
- A formal `review_corpus_version`

The cursor is opaque to the browser and must be validated before use. A mismatch or stale corpus version returns a stable invalid/stale-cursor response so the frontend can restart from page one.

The repository applies place, rating, and sort before the keyset predicate. Existing null-last rules and the review-ID tie breaker remain mandatory. Page size defaults to 20 and is capped at 50.

### 19.3 Corpus version

Add `review_corpus_version` to the place or a dedicated review-collection state row. Increment it when:

- A canonical review is inserted
- A material review field changes
- Reviews for the place are deleted
- A deduplication merge changes visible membership

Topic-only changes do not invalidate review cursors. This version can later support reviewer-label and semantic-result caching.

### 19.4 Upstream fetch-older operation

Add:

```http
POST /api/v1/restaurants/{place_id}/reviews/load-more
Idempotency-Key: <client-generated key>

{
  "additional_target_count": 50,
  "confirm_cost": true
}
```

The backend owns the provider cursor; the browser does not send a raw SerpApi token. The service:

1. Reads the latest resumable collection state.
2. Estimates the maximum additional provider searches.
3. Uses BL-007 confirmation, idempotency, budget reservation, and per-place locking.
4. Requests complete provider pages and commits each page plus the next cursor.
5. Does not use the known-unchanged refresh shortcut.
6. Stops at the approved additional target, pagination end, cancellation, or reserved limit.
7. Returns collected-new count, total stored count, provider request counts, stop reason, and whether another fetch is possible.

If a stored provider cursor has expired, return a recovery choice. A confirmed recovery restarts newest-first, deduplicates observed reviews, and walks forward without discarding stored data.

### 19.5 Frontend state

- Use a TanStack infinite query for deterministic stored pages.
- Reset pages when restaurant, exact rating, or sort changes.
- Preserve appended pages and scroll position when moving between the search-results and review surfaces.
- After sync, refresh, deletion, or fetch-older changes the corpus version, invalidate all pages for that restaurant.
- Show a free `Show more saved reviews` action only when `has_more` is true.
- Show `Fetch older reviews` separately when provider collection may continue.
- Display estimated searches before confirmation and actual new/stored counts after completion.

Semantic filtering remains bounded to its current candidate maximum in BL-008. It must not call the LLM once per display page. Pagination of larger semantic result sets requires a versioned filter-result session or shared cache.

### 19.6 Tests

Backend tests cover every sort, equal sort values, null dates/ratings, exact-star filtering, stale and tampered cursors, deletion, corpus changes, and final empty pages. Integration tests cover provider-cursor resume, expired-cursor recovery, per-page commits, idempotency, and budget exhaustion. Playwright tests cover append behavior, preserved scroll, mobile navigation, action labels, and proof that saved-page loading does not change provider usage.

## 20. Planned Feature: Rich Review Data

Backlog tracking: [`BL-009 — Rich review data`](backlog.md#bl-009--rich-review-data). The backlog status is authoritative.

### 20.1 Provider fields

For each SerpApi review, ingest:

```json
{
  "details": {
    "meal_type": "Delivery",
    "price_per_person": "$10–20",
    "food": 5,
    "service": 5,
    "recommended_dishes": ["Regular", "Grandma"]
  },
  "translated_details": {},
  "images": ["https://provider-image.example/..."]
}
```

The actual `details` keys are dynamic. Preserve the raw map, accept only JSON-compatible scalar/list values within size limits, and normalize recognized aliases for display. Unknown safe keys remain available for generic rendering. Invalid rich fields must not discard the base review.

### 20.2 Persistence model

Add canonical review fields:

```text
reviews
- details JSONB nullable
- translated_details JSONB nullable
- rich_data_updated_at nullable
```

Retain provider provenance:

```text
review_origins
- provider_details JSONB nullable
- provider_translated_details JSONB nullable
```

Add ordered images:

```text
review_images
- id
- review_id
- review_origin_id
- provider_name
- provider_image_url
- position
- active
- first_seen_at
- last_seen_at
```

The image uniqueness rule is scoped to origin and provider URL. A new provider snapshot marks missing images inactive instead of deleting history immediately. PostgreSQL stores metadata and URLs only, not image binaries.

Canonical precedence follows the existing provider rules: Google-official canonical values win where the official resource supplies an equivalent field; otherwise SerpApi may populate the richer canonical display snapshot. Missing fallback data never clears valid SerpApi rich data.

### 20.3 Material-change and deduplication behavior

Normalize maps recursively with deterministic key ordering for comparison. Treat as material:

- A structured key/value added, removed, or changed
- A translated detail added, removed, or changed
- An image added, removed, replaced, or reordered

These changes reset the known-unchanged refresh streak and update the canonical review without creating a duplicate. Rich data is not part of the fallback identity match unless required to disambiguate otherwise identical candidates.

### 20.4 API schema

Review responses add optional defaults:

```json
{
  "details": {},
  "translated_details": {},
  "images": [
    {
      "url": "https://...",
      "position": 0,
      "provider": "serpapi"
    }
  ]
}
```

Empty maps and lists preserve compatibility for Google fallback and older stored rows. API responses enforce field-count, value-length, image-count, and URL-length limits.

### 20.5 Review-card rendering

Render recognized fields in this order when present:

1. Order/service type
2. Meal type
3. Price per person
4. Food, service, and atmosphere sub-ratings
5. Recommended dishes
6. Dietary, parking, accessibility, seating, and other details

Use human-readable labels derived from an allowlisted key map. Remaining safe unknown keys render through a generic label/value row. Prefer translated values for the configured language and retain original values for fallback or disclosure.

Images render in an optional horizontally scrollable gallery:

- Lazy loading and reserved dimensions to avoid layout shift
- Broken-image fallback
- No automatic binary download or PostgreSQL storage
- Direct review/source link and provider attribution
- Keyboard-accessible expansion if a lightbox is introduced

Do not use the LLM to invent image captions, infer missing structured values, or turn review details into restaurant-level facts.

### 20.6 URL and content safety

- Accept HTTPS URLs only.
- Validate supported provider image hosts before rendering.
- Render structured values as text, never raw HTML.
- Do not proxy or cache images until provider terms, cache lifetime, attribution, and deletion behavior have been reviewed.
- Expect remote URLs to expire and keep the rest of the review usable.

### 20.7 Migration and tests

The Alembic migration adds nullable/default-compatible fields and backfills no invented data. Provider fixtures cover complete, partial, translated, unknown, malformed, and missing structures. Refresh tests cover added/removed details and images. API and frontend tests cover safe generic rendering, ordering, long values, broken images, empty fallbacks, keyboard use, and mobile overflow.

## 21. Planned Feature: Private Oracle and Tailscale Deployment

Backlog tracking: [`BL-010 — Private Oracle and Tailscale deployment`](backlog.md#bl-010--private-oracle-and-tailscale-deployment). The backlog status is authoritative. This work is deliberately lower priority than BL-007 through BL-009.

### 21.1 Target boundary

The Oracle VM hosts the always-on frontend, FastAPI backend, and PostgreSQL database. The home Linux machine continues hosting the OpenAI-compatible LLM. All user and LLM traffic stays inside the Tailnet.

```text
Approved family device
        │ HTTPS over Tailnet
        ▼
Oracle VM: private ingress/reverse proxy
        ├── frontend
        ├── FastAPI
        └── PostgreSQL (Docker network only)
                  │
                  │ Tailscale ACL/grant
                  ▼
Home Linux LLM endpoint
```

The Raspberry Pi remains a homelab device and is not part of the production request path.

### 21.2 Oracle host preparation

- Create a non-root deployment account and use key-based or Tailnet administration.
- Install Docker Engine/Compose and Tailscale from supported sources.
- Join the VM with a dedicated tagged machine identity.
- Keep OS security updates, time synchronization, disk monitoring, and log rotation enabled.
- Use Oracle network rules and the host firewall as deny-by-default layers.
- Do not expose PostgreSQL, FastAPI, Vite, or the LLM publicly.
- Retain only the minimum administration/bootstrap path required by the chosen Tailscale setup.

Exact Oracle image, firewall, and Tailscale installation commands must be revalidated against current vendor documentation during implementation.

### 21.3 Tailnet ingress and TLS

Publish one Tailnet-only HTTPS origin such as:

```text
https://real-reviews.<tailnet-name>.ts.net
```

Use a Tailnet HTTPS/reverse-proxy mechanism to route:

- `/` to the production frontend
- `/api/` to FastAPI
- `/health` only as required for private monitoring

Prefer same-origin frontend/API requests in production so public CORS is unnecessary. Bind container-published ingress ports to loopback or a private interface and keep PostgreSQL exclusively on the Compose network.

Tailscale grants/ACLs should express:

- Approved family users/devices may reach the application HTTPS service.
- The Oracle API machine identity may reach only the home LLM host/port it requires.
- Family clients cannot reach the LLM port directly.
- Unrelated Tailnet devices receive no implicit application or LLM access.

### 21.4 Production Compose and release flow

Deploy with the base and production Compose files:

```bash
docker compose -f docker/compose.yaml -f docker/compose.prod.yaml config
docker compose -f docker/compose.yaml -f docker/compose.prod.yaml run --rm migrate
docker compose -f docker/compose.yaml -f docker/compose.prod.yaml up -d
```

Production requirements:

- Immutable versioned images
- No source-code bind mounts
- No host PostgreSQL port
- Health checks and restart policies
- One API replica until BL-007 supports shared concurrency
- Explicit migration before application cutover
- Previous known-good image tags retained for rollback
- Deployment version and migration revision recorded

An automated pipeline may later build and publish images, but the first family deployment may use a documented manual release procedure.

### 21.5 Secrets and configuration

- Do not commit or copy the development `.env` as the production secret store.
- Provide separate Google server/browser keys with production restrictions.
- Keep the SerpApi key and any LLM credential available only to FastAPI.
- Set the production frontend origin/API base to the private HTTPS origin.
- Configure the LLM base URL using its Tailnet hostname and private port.
- Restrict secret-file permissions and document rotation.
- Redact credentials and provider URLs containing secrets from logs.

### 21.6 Data durability

The PostgreSQL named volume persists through container replacement but is not a backup. Before family use:

- Create scheduled encrypted PostgreSQL backups outside the active database volume.
- Define retention and available disk thresholds.
- Perform and document a restore into a clean database.
- Record Alembic revision with each backup.
- Test container/VM reboot, database health recovery, and application restart.
- Document Oracle volume or VM failure recovery.

### 21.7 LLM availability

The Oracle API calls the home LLM through Tailscale. Review search, saved-review browsing, deterministic filters, synchronization, and topics continue working when the LLM or home internet is unavailable. Semantic operations return a clear retryable error and preserve deterministic results.

No inbound public port is opened on the home network. If direct Oracle-to-home calls prove unreliable, a future outbound home worker/job-queue design may replace them without changing the public/private application API.

### 21.8 Family and future iOS access

Family devices install Tailscale and access the responsive web app in Safari or from its Home Screen icon. The private HTTPS origin is required for the installed web experience. There is one shared React frontend, not a second mobile implementation.

A future native iOS application can reuse the private FastAPI contract over the Tailnet. Native distribution, TestFlight, App Store enrollment, and Swift/Flutter/React Native work remain outside BL-010.

### 21.9 Deployment acceptance

- Approved family Tailnet devices can reach the HTTPS app.
- Non-Tailnet clients cannot reach it.
- Oracle can reach the home LLM, while family clients cannot access the LLM directly.
- PostgreSQL has no public or Tailnet host port.
- Frontend/API traffic uses one private HTTPS origin.
- Restart, migration, rollback, backup, restore, secret rotation, and LLM-offline procedures are exercised.
- Logs provide request/operation IDs without review text, author data, coordinates, or credentials.

## References

- [Google Places Autocomplete (New)](https://developers.google.com/maps/documentation/places/web-service/place-autocomplete)
- [Google Place Autocomplete Widget](https://developers.google.com/maps/documentation/javascript/place-autocomplete-new)
- [Google Autocomplete session pricing](https://developers.google.com/maps/documentation/javascript/session-pricing)
- [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing)
- [Google Place Details field/SKU classifications](https://developers.google.com/maps/documentation/places/web-service/place-details)
- [Google Places review schema](https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places)
- [Google Places policies and attribution](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Google Maps Platform Terms](https://cloud.google.com/maps-platform/terms)
- [SerpApi Google Maps Reviews API](https://serpapi.com/google-maps-reviews-api)
- [SerpApi Google Maps Contributor Reviews API](https://serpapi.com/google-maps-contributor-reviews-api)
- [SerpApi pricing](https://serpapi.com/pricing)
- [SerpApi legal terms](https://serpapi.com/legal)
- [uv projects and dependency locking](https://docs.astral.sh/uv/concepts/projects/sync/)
- [Using uv in Docker](https://docs.astral.sh/uv/guides/integration/docker/)
- [Docker Compose file merging and overrides](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
