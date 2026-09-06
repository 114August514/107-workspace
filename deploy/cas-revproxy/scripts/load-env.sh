# Shared by run-auth.sh / render-nginx.sh. Sourced, not executed.
# Loads repository .env files first, then this directory's env overlay.

CAS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$CAS_ROOT/../.." && pwd)"

_load_env_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$file"
    set +a
  fi
}

_load_env_file "$REPO_ROOT/.env"
_load_env_file "$REPO_ROOT/backend/.env"
_load_env_file "$CAS_ROOT/env"

export SECRET_KEY="${SECRET_KEY:-${WORKSPACE107_AUTH_SECRET_KEY:-}}"
export PUBLIC_ORIGIN="${PUBLIC_ORIGIN:-${WORKSPACE107_PUBLIC_ORIGIN:-http://127.0.0.1:5174}}"
export SESSION_COOKIE_SECURE="${SESSION_COOKIE_SECURE:-${WORKSPACE107_SESSION_COOKIE_SECURE:-0}}"
export HTTPS_PROXY="${HTTPS_PROXY:-${WORKSPACE107_HTTPS_PROXY:-}}"
export CAS_LOGIN_URL="${CAS_LOGIN_URL:-${WORKSPACE107_CAS_LOGIN_URL:-https://passport.ustc.edu.cn/login}}"
export CAS_VALIDATE_URL="${CAS_VALIDATE_URL:-${WORKSPACE107_CAS_VALIDATE_URL:-https://passport.ustc.edu.cn/serviceValidate}}"
export LOCAL_ADMIN_USERNAME="${LOCAL_ADMIN_USERNAME:-${WORKSPACE107_LOCAL_ADMIN_USERNAME:-platform-admin}}"
export LOCAL_ADMIN_DISPLAY_NAME="${LOCAL_ADMIN_DISPLAY_NAME:-${WORKSPACE107_LOCAL_ADMIN_DISPLAY_NAME:-平台管理员}}"
export LOCAL_ADMIN_PASSWORD="${LOCAL_ADMIN_PASSWORD:-${WORKSPACE107_LOCAL_ADMIN_PASSWORD:-}}"
export LOCAL_ADMIN_PASSWORD_HASH="${LOCAL_ADMIN_PASSWORD_HASH:-${WORKSPACE107_LOCAL_ADMIN_PASSWORD_HASH:-}}"
export BACKEND_ORIGIN="${BACKEND_ORIGIN:-${WORKSPACE107_BACKEND_ORIGIN:-http://127.0.0.1:8000}}"
export AUTH_ORIGIN="${AUTH_ORIGIN:-${WORKSPACE107_AUTH_ORIGIN:-http://127.0.0.1:8108}}"
export NGINX_LISTEN="${NGINX_LISTEN:-127.0.0.1:8107}"
