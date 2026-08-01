#!/usr/bin/env bash
# 同步前后端接口契约。
#
#     后端 DTO / 路由
#            ↓  workspace107.tools.export_openapi
#     docs/api/openapi.json
#            ↓  openapi-typescript
#     frontend/src/api/schema.d.ts
#            ↓  派生
#     frontend/src/api/types.ts → 组件
#
# 改了后端 DTO 或路由之后执行这个脚本，并把两个生成物一起提交。
# CI 的 api-contract-check 会重新生成并检查是否存在未提交差异——
# 也就是说，前端类型不可能悄悄和后端脱节。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACT="$REPO_ROOT/docs/api/openapi.json"
SCHEMA="$REPO_ROOT/frontend/src/api/schema.d.ts"

mkdir -p "$(dirname "$CONTRACT")"

cd "$REPO_ROOT/backend"
uv run python -m workspace107.tools.export_openapi "$CONTRACT"

cd "$REPO_ROOT/frontend"
[ -d node_modules ] || npm ci --silent
npm run --silent generate:api

echo "已同步："
echo "  $CONTRACT"
echo "  $SCHEMA"
