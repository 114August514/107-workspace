#!/usr/bin/env bash
# 本地自检：与 CI 执行同一组命令。
# 提交 PR 之前跑一遍，避免把能在本地发现的问题推到 CI。
#
#   ./scripts/check.sh              全部检查
#   ./scripts/check.sh backend      只检查后端
#   ./scripts/check.sh frontend     只检查前端
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"
FAILED=()

step() {
  printf '\n\033[1;34m==> %s\033[0m\n' "$1"
}

run() {
  local label="$1"
  shift
  if "$@"; then
    printf '\033[0;32m    ok  %s\033[0m\n' "$label"
  else
    printf '\033[0;31m    FAIL %s\033[0m\n' "$label"
    FAILED+=("$label")
  fi
}

check_backend() {
  step "backend"
  cd "$REPO_ROOT/backend"
  uv sync --all-extras --quiet
  run "backend-lint (ruff check)"   uv run ruff check .
  run "backend-lint (ruff format)"  uv run ruff format --check .
  run "backend-test (pytest)"       uv run pytest -q
}

check_frontend() {
  step "frontend"
  cd "$REPO_ROOT/frontend"
  [ -d node_modules ] || npm ci
  run "frontend-format"     npm run --silent format:check
  run "frontend-lint"       npm run --silent lint
  run "frontend-typecheck"  npm run --silent typecheck
  run "frontend-test"       npm run --silent test -- --run
  run "frontend-build"      npm run --silent build
}

check_contract() {
  step "api-contract-check"
  cd "$REPO_ROOT"
  "$REPO_ROOT/scripts/sync-api-contract.sh" >/dev/null
  # 两个生成物都要检查：只对 openapi.json 把关的话，
  # 前端类型仍然可能和后端脱节。
  local generated=(docs/api/openapi.json frontend/src/api/schema.d.ts)
  if git diff --quiet -- "${generated[@]}"; then
    printf '\033[0;32m    ok  接口契约与前端类型均与后端一致\033[0m\n'
  else
    printf '\033[0;31m    FAIL 生成物存在未提交差异：\033[0m\n'
    git diff --name-only -- "${generated[@]}" | sed 's/^/      /'
    FAILED+=("api-contract-check")
  fi
}

case "$TARGET" in
  backend)  check_backend ;;
  frontend) check_frontend ;;
  all)      check_backend; check_frontend; check_contract ;;
  *)        echo "用法: $0 [all|backend|frontend]" >&2; exit 2 ;;
esac

printf '\n'
if [ ${#FAILED[@]} -eq 0 ]; then
  printf '\033[0;32m全部检查通过。\033[0m\n'
else
  printf '\033[0;31m以下检查失败：\033[0m\n'
  printf '  - %s\n' "${FAILED[@]}"
  exit 1
fi
