COMPOSE_DEV := docker compose -f docker/compose.yaml -f docker/compose.override.yaml
COMPOSE_PROD := docker compose -f docker/compose.yaml -f docker/compose.prod.yaml

.PHONY: help up up-detached down down-volumes restart ps logs build config prod-config migrate api-lint api-test frontend-lint frontend-test frontend-e2e test frontend-build clean-images

help:
	@echo "Real Reviews Docker commands"
	@echo "  make up              Build and start the dev stack in the foreground"
	@echo "  make up-detached     Build and start the dev stack in the background"
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
	@echo "  make frontend-build  Build frontend production target"
	@echo "  make test            Run backend and frontend tests"
	@echo "  make config          Validate dev Compose config"
	@echo "  make prod-config     Validate prod Compose config"

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
	$(COMPOSE_DEV) config

prod-config:
	$(COMPOSE_PROD) config

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

frontend-build:
	docker build --target build -t real-reviews-frontend-build ./frontend

test: api-test frontend-test

clean-images:
	docker image rm real-reviews-api-dev real-reviews-migrate-dev real-reviews-frontend-dev real-reviews-frontend-build 2>/dev/null || true
