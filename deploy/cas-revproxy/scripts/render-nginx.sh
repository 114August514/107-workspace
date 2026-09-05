#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/load-env.sh"

if [[ -z "${FRONTEND_DIST:-}" ]]; then
  echo "FRONTEND_DIST is required for nginx (set it in deploy/cas-revproxy/env)" >&2
  exit 1
fi

mkdir -p "$ROOT/runtime/logs" "$ROOT/runtime/temp" "$ROOT/runtime/conf"
envsubst '${NGINX_LISTEN} ${FRONTEND_DIST} ${AUTH_ORIGIN} ${BACKEND_ORIGIN}' \
  < "$ROOT/nginx.conf.template" \
  > "$ROOT/runtime/conf/nginx.conf"

if [[ -f /etc/nginx/mime.types ]]; then
  ln -sfn /etc/nginx/mime.types "$ROOT/runtime/conf/mime.types"
fi
echo "wrote $ROOT/runtime/conf/nginx.conf"
