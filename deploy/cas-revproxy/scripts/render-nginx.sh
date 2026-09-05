#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/env" ]]; then
  echo "missing $ROOT/env; copy env.example and fill values" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/env"
set +a

mkdir -p "$ROOT/runtime/logs" "$ROOT/runtime/temp" "$ROOT/runtime/conf"
envsubst '${NGINX_LISTEN} ${FRONTEND_DIST} ${AUTH_ORIGIN} ${BACKEND_ORIGIN}' \
  < "$ROOT/nginx.conf.template" \
  > "$ROOT/runtime/conf/nginx.conf"

if [[ -f /etc/nginx/mime.types ]]; then
  ln -sfn /etc/nginx/mime.types "$ROOT/runtime/conf/mime.types"
fi
echo "wrote $ROOT/runtime/conf/nginx.conf"
