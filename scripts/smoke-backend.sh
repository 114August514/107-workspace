#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/backend"

tmp_dir="$(mktemp -d)"
server_pid=""
server_log="$tmp_dir/uvicorn.log"
port="${WORKSPACE107_SMOKE_PORT:-8760}"

cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

export WORKSPACE107_DATABASE_URL="sqlite+aiosqlite:///$tmp_dir/workspace107.db"
export WORKSPACE107_STORAGE_ROOT="$tmp_dir/storage"
export WORKSPACE107_MOCK_CLUSTER_ROOT="$tmp_dir/mock-cluster"
export WORKSPACE107_TRANSFER_ROOTS="{\"source\":\"$tmp_dir/transfer/source\",\"cluster\":\"$tmp_dir/transfer/cluster\",\"downloads\":\"$tmp_dir/transfer/downloads\"}"
export WORKSPACE107_CLUSTER_ADAPTER="mock"
export WORKSPACE107_CLUSTER_TRANSPORT="local"
export WORKSPACE107_RECONCILE_INTERVAL_SECONDS="0.02"

uv run alembic upgrade head
uv run uvicorn workspace107.main:create_app \
  --factory \
  --host 127.0.0.1 \
  --port "$port" \
  >"$server_log" 2>&1 &
server_pid=$!

ready="false"
for _ in {1..100}; do
  if ! kill -0 "$server_pid" 2>/dev/null; then
    cat "$server_log"
    wait "$server_pid"
  fi
  if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
    ready="true"
    break
  fi
  sleep 0.05
done

if [[ "$ready" != "true" ]]; then
  cat "$server_log"
  printf 'backend did not become ready on port %s\n' "$port" >&2
  exit 1
fi

WORKSPACE107_TEST_BASE_URL="http://127.0.0.1:$port" \
WORKSPACE107_TEST_SOURCE_ROOT="$tmp_dir/transfer/source" \
  uv run pytest tests/smoke/test_http_workflow.py -q
