#!/usr/bin/env bash
set -euo pipefail

# Builds the production frontend image and runs the prod-smoke Playwright spec
# against it. Catches prod-only regressions the dev e2e cannot see:
#   - the served CSP blocking Google Maps fonts / icons / the Places API
#   - VITE_GOOGLE_MAPS_BROWSER_API_KEY not being baked into the bundle
# Uses a dummy key when SMOKE_KEY is unset; needs outbound network to Google.

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

SMOKE_KEY=${SMOKE_KEY:-ci-smoke-key}
PORT=${SMOKE_PORT:-8080}
CONTAINER=rr-smoke-frontend

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Building production frontend image (browser key baked)"
docker build --target production \
  --build-arg VITE_REVIEWER_CONTEXT_ENABLED=false \
  --build-arg VITE_GOOGLE_MAPS_BROWSER_API_KEY="$SMOKE_KEY" \
  -t real-reviews-frontend-prod-e2e ./frontend

cleanup
docker run -d --name "$CONTAINER" \
  --add-host api:127.0.0.1 \
  -p "$PORT:80" \
  real-reviews-frontend-prod-e2e

echo "Waiting for $CONTAINER on http://127.0.0.1:$PORT …"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$PORT/" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "http://127.0.0.1:$PORT/" >/dev/null

echo "Running prod-smoke Playwright spec …"
# --network host so 127.0.0.1:$PORT inside the container reaches the host port.
docker run --rm --network host \
  -e PLAYWRIGHT_BASE_URL="http://127.0.0.1:$PORT" \
  -e PROD_SMOKE=1 \
  -v "$repo_root/frontend:/app" \
  -v rr-smoke-node_modules:/app/node_modules \
  -v rr-smoke-pnpm-store:/pnpm/store \
  mcr.microsoft.com/playwright:v1.62.1-noble \
  sh -c 'cd /app && corepack enable && corepack prepare pnpm@9.15.4 --activate && pnpm install --frozen-lockfile --store-dir /pnpm/store && pnpm exec playwright test --project=prod-smoke'

echo "Prod smoke test passed."
