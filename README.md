# Real Reviews

Personal restaurant review research tool using local LLM for better filtering. Made completely with Codex.

## Project documentation

- [`design_doc.md`](design_doc.md) describes the current product boundaries, architecture, implemented behavior, and known implementation work.
- [`backlog.md`](backlog.md) is the source of truth for intentionally deferred features and future ideas.

Add future feature requests to `backlog.md`. A backlog item is not implemented unless its status says `Done`.

## First run

```bash
cp .env.example .env
make up
```

Frontend: http://localhost:5173
API health: http://localhost:8000/health

To stop the app without deleting the database volume:

```bash
make down
```

To stop the app and remove Docker volumes, including the local Postgres data:

```bash
make down-volumes
```

## Container-only workflow

```bash
make migrate
make api-lint
make frontend-test
make down
```

Do not install dependencies on the host; keep `frontend/node_modules` and `backend/.venv` in Docker volumes only.
