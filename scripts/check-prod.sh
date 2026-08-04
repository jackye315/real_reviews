#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

compose=(docker compose --env-file .env -f docker/compose.yaml -f docker/compose.prod.yaml)
required_services=(postgres api frontend proxy certbot-renew)
failures=0

for service in "${required_services[@]}"; do
  container_id=$("${compose[@]}" ps -q "$service")
  if [[ -z "$container_id" ]]; then
    echo "FAIL: $service is not running" >&2
    failures=$((failures + 1))
    continue
  fi

  state=$(docker inspect --format '{{.State.Status}}' "$container_id")
  health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")
  if [[ "$state" != "running" || "$health" == "unhealthy" ]]; then
    echo "FAIL: $service state=$state health=$health" >&2
    failures=$((failures + 1))
  fi
done

if ! tailscale status --self >/dev/null 2>&1; then
  echo "FAIL: Tailscale is not connected" >&2
  failures=$((failures + 1))
fi

app_domain=$(awk -F= '$1 == "APP_DOMAIN" {print $2}' .env)
cert_min_validity_seconds=${CERT_MIN_VALIDITY_SECONDS:-1209600}
if [[ -z "$app_domain" ]] || ! openssl s_client -connect "$app_domain:443" -servername "$app_domain" </dev/null 2>/dev/null \
  | openssl x509 -checkend "$cert_min_validity_seconds" -noout >/dev/null 2>&1; then
  echo "FAIL: TLS certificate is unavailable or expires within 14 days" >&2
  failures=$((failures + 1))
fi

disk_usage_max_percent=${DISK_USAGE_MAX_PERCENT:-85}
disk_usage_percent=$(df -P "$repo_root" | awk 'NR == 2 {gsub(/%/, "", $5); print $5}')
if (( disk_usage_percent >= disk_usage_max_percent )); then
  echo "FAIL: filesystem usage is ${disk_usage_percent}% (threshold ${disk_usage_max_percent}%)" >&2
  failures=$((failures + 1))
fi

if (( failures > 0 )); then
  exit 1
fi

echo "Production checks passed: containers, Tailscale, TLS, and disk usage"
