#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/load-env.sh"

if [[ -z "${SECRET_KEY:-}" ]]; then
  echo "SECRET_KEY or WORKSPACE107_AUTH_SECRET_KEY is required (set it in backend/.env)" >&2
  exit 1
fi

if [[ -z "${HTTPS_PROXY:-}" ]]; then
  echo "warning: HTTPS_PROXY is empty; CAS serviceValidate will fail. Password login still works." >&2
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install "flask>=3,<4"
fi

export FLASK_APP="auth.auth_server:create_app"
exec "$ROOT/.venv/bin/flask" run --host 127.0.0.1 --port 8108
