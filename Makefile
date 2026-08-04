# Compose resolves interpolation relative to the first compose file (docker/), so
# explicitly load the repository-root .env for both interpolation and env_file.
COMPOSE_DEV := docker compose --env-file .env -f docker/compose.yaml -f docker/compose.dev.yaml
COMPOSE_PROD := docker compose --env-file .env -f docker/compose.yaml -f docker/compose.prod.yaml

# Browser key for the prod smoke test image. Default to a dummy: the smoke
# test validates CSP coverage and that autocomplete requests fire, not
# authenticated Google responses, so a billable key adds no coverage. For a
# live integration run, opt in explicitly:
#   make frontend-e2e-prod SMOKE_KEY=<your-key>
SMOKE_KEY ?= ci-smoke-key

.PHONY: help up down down-volumes restart ps logs build config up-prod down-prod ps-prod logs-prod config-prod cert-prod check-prod migrate api-lint api-test frontend-lint frontend-test frontend-e2e frontend-e2e-prod test frontend-build clean-images

help:
	@echo "Real Reviews Docker commands"
	@echo "  make up              Build and start the development stack"
	@echo "  make down            Stop and remove dev containers (keeps DB volume)"
	@echo "  make down-volumes    Stop and remove dev containers and volumes"
	@echo "  make restart         Restart the dev stack"
	@echo "  make ps              Show container status"
	@echo "  make logs            Follow dev stack logs"
	@echo "  make build           Build dev images"
	@echo "  make migrate         Run Alembic migrations"
	@echo "  make api-lint        Run backend Ruff"
	@echo "  make api-test        Run backend tests"
	@echo "  make frontend-lint   Run frontend ESLint"
	@echo "  make frontend-test   Run frontend tests"
	@echo "  make frontend-e2e    Run Playwright responsive browser tests"
	@echo "  make frontend-e2e-prod  Run Playwright smoke test against the production image"
	@echo "  make frontend-build  Build frontend production target"
	@echo "  make test            Run backend and frontend tests"
	@echo "  make config          Validate dev Compose config"
	@echo "  make up-prod         Issue TLS and start the production stack"
	@echo "  make down-prod       Stop the production stack"
	@echo "  make ps-prod         Show production container status"
	@echo "  make logs-prod       Follow production logs"
	@echo "  make config-prod     Validate the production Compose config"
	@echo "  make cert-prod       Issue/refresh the production TLS certificate"
	@echo "  make check-prod      Check containers, Tailscale, TLS, and disk usage"

up:
	$(COMPOSE_DEV) up --build -d

down:
	$(COMPOSE_DEV) down

down-volumes:
	$(COMPOSE_DEV) down --volumes --remove-orphans

restart: down up

ps:
	$(COMPOSE_DEV) ps

logs:
	$(COMPOSE_DEV) logs -f

build:
	$(COMPOSE_DEV) build api migrate frontend

config:
	$(COMPOSE_DEV) config --quiet

config-prod:
	$(COMPOSE_PROD) config --quiet

cert-prod:
	$(COMPOSE_PROD) --profile tools run --rm certbot

up-prod: cert-prod
	$(COMPOSE_PROD) up --build -d --remove-orphans

down-prod:
	$(COMPOSE_PROD) down

ps-prod:
	$(COMPOSE_PROD) ps

logs-prod:
	$(COMPOSE_PROD) logs -f

check-prod:
	./scripts/check-prod.sh

migrate:
	$(COMPOSE_DEV) run --rm migrate uv run alembic upgrade head

api-lint:
	docker run --rm real-reviews-api-dev uv run ruff check .

api-test:
	docker run --rm real-reviews-api-dev uv run pytest

frontend-lint:
	docker run --rm real-reviews-frontend-dev pnpm lint

frontend-test:
	docker run --rm real-reviews-frontend-dev pnpm test

frontend-e2e:
	$(COMPOSE_DEV) --profile e2e run --rm e2e

# Builds the production frontend image and runs the prod-smoke Playwright spec
# against it (see scripts/smoke-prod.sh). Catches prod-only regressions (CSP
# blocking Google Maps resources, VITE_GOOGLE_MAPS_BROWSER_API_KEY not baked)
# that the dev e2e cannot see.
frontend-e2e-prod:
	@SMOKE_KEY=$(SMOKE_KEY) bash scripts/smoke-prod.sh

frontend-build:
	docker build --target build -t real-reviews-frontend-build ./frontend

test: api-test frontend-test

clean-images:
	docker image rm real-reviews-api-dev real-reviews-migrate-dev real-reviews-frontend-dev real-reviews-frontend-build 2>/dev/null || true
