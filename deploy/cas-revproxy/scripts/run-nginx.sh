#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$ROOT/scripts/render-nginx.sh"

NGINX_BIN="${NGINX_BIN:-$HOME/opt/nginx/usr/sbin/nginx}"
if [[ ! -x "$NGINX_BIN" ]]; then
  echo "nginx not found at $NGINX_BIN" >&2
  exit 1
fi
exec "$NGINX_BIN" -p "$ROOT/runtime" -c "$ROOT/runtime/conf/nginx.conf"
