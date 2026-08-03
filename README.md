# Real Reviews

Personal restaurant review research tool using local LLM for better filtering. Made completely with Codex.

## Project documentation

- [`design_doc.md`](design_doc.md) describes the current product boundaries, architecture, implemented behavior, and known implementation work.
- [`backlog.md`](backlog.md) is the source of truth for intentionally deferred features and future ideas.

Add future feature requests to `backlog.md`. A backlog item is not implemented unless its status says `Done`.

## Run locally

### Prerequisites

- Git
- Docker Engine with the Docker Compose plugin, or Docker Desktop
- GNU Make

Install Docker from the [official Docker Engine](https://docs.docker.com/engine/install/) or [Docker Desktop](https://docs.docker.com/desktop/) documentation. Application dependencies run inside containers; do not install frontend or backend packages directly on the host.

### 1. Clone and configure

```bash
git clone <repository-url>
cd real_reviews
cp .env.example .env
```

Edit `.env` and keep it out of version control. The Compose defaults are sufficient for PostgreSQL and the local development URLs. Configure the integrations needed for the features you plan to use:

- `VITE_GOOGLE_MAPS_BROWSER_API_KEY` loads Google Places autocomplete in the browser.
- `GOOGLE_MAPS_SERVER_API_KEY` enables server-side Google Places requests.
- `SERPAPI_API_KEY` enables saved-review acquisition through SerpApi.
- `REVIEW_CURSOR_SIGNING_KEY` signs saved-review pagination cursors. The development default is acceptable only for local use.

The app will start without all integration keys, but the corresponding search or review features will report that they are unavailable.

To enable local dish summaries and semantic LLM features, configure an OpenAI-compatible endpoint:

```dotenv
LOCAL_DISH_SUMMARY_ENABLED=true
LLM_BASE_URL=http://host.docker.internal:8000/v1
LLM_MODEL=your-model-name
LLM_API_KEY=
```

`LLM_BASE_URL` must be reachable from inside the API container and expose `/chat/completions` beneath the configured `/v1` base. On Docker Desktop, `host.docker.internal` reaches a model server running on the host. On Linux, use an address reachable from the Docker network, such as the host's LAN or private-network address. Do not use `localhost` for a model running on the host because `localhost` inside the API container refers to that container itself.

### 2. Start the development stack

```bash
make up
```

`make up` builds the images and runs the stack in the foreground. To run it in the background instead:

```bash
make up-detached
```

Open:

- Frontend: <http://localhost:5173>
- API health check: <http://localhost:8000/health>

Useful development commands:

```bash
make ps       # show container status
make logs     # follow container logs
make restart  # restart the development stack
```

The startup sequence waits for PostgreSQL, runs all pending Alembic migrations, and then starts the API and frontend. Database data persists in the `postgres_data` Docker volume across ordinary restarts.

### 3. Stop or reset

To stop the app without deleting the database volume:

```bash
make down
```

To stop the app and remove Docker volumes, including the local Postgres data:

```bash
make down-volumes
```

`make down-volumes` permanently removes the local PostgreSQL data along with the development volumes. Use it only when you intentionally want a clean database.

### Troubleshooting

- Run `make logs` and check the `migrate`, `api`, and `frontend` services if startup fails.
- If Google autocomplete is unavailable, confirm the browser key is present in `.env`, then restart the frontend stack.
- If the UI says the local LLM is unavailable, confirm the endpoint and model name, then verify the endpoint is reachable from the API container rather than only from the host.
- Validate the merged development Compose configuration with `make config`.

## Container-only workflow

```bash
make migrate
make api-lint
make frontend-test
make frontend-e2e
make down
```

The test and lint commands use containerized dependencies. Keep `frontend/node_modules` and `backend/.venv` in Docker volumes only.
