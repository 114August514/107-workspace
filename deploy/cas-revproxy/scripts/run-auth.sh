#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/env" ]]; then
  echo "missing $ROOT/env; copy env.example and fill SECRET_KEY" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/env"
set +a

if [[ -z "${HTTPS_PROXY:-}" ]]; then
  echo "warning: HTTPS_PROXY is empty; CAS serviceValidate will fail. Password login still works." >&2
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install "flask>=3,<4"
fi

export FLASK_APP="auth.auth_server:create_app"
exec "$ROOT/.venv/bin/flask" run --host 127.0.0.1 --port 8108
