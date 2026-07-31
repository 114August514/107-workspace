#!/usr/bin/env bash
# 端到端演示：跑通 M1 核心运行闭环。
#
#   创建 Project -> 保存版本 -> 配置运行方案 -> 提交 Run
#   -> 查看状态 -> 查看日志 -> 取回 Artifact
#
# 全程用 mock 调度器在本机以子进程真实执行，不需要连接集群。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKDIR="$(mktemp -d)"
PORT="${PORT:-8107}"
BASE="http://127.0.0.1:${PORT}/api/v1"
USER_HEADER="X-User: demo"
SERVER_PID=""

cleanup() {
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$1"; }

need() {
  command -v "$1" >/dev/null || { echo "需要 $1，请先安装" >&2; exit 1; }
}
need uv
need curl
need python3

api() {
  local method="$1" path="$2"
  shift 2
  curl -sS -X "$method" "${BASE}${path}" -H "$USER_HEADER" -H 'Content-Type: application/json' "$@"
}

jget() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }

say "准备隔离环境：$WORKDIR"
cd "$REPO_ROOT/backend"
export WORKSPACE107_ENV=local
export WORKSPACE107_DATABASE_URL="sqlite+aiosqlite:///${WORKDIR}/demo.db"
export WORKSPACE107_STORAGE_ROOT="${WORKDIR}/storage"
export WORKSPACE107_SCHEDULER=mock

uv sync --all-extras --quiet
uv run alembic upgrade head >/dev/null
uv run python -m workspace107.tools.seed >/dev/null

say "启动服务 :${PORT}"
uv run uvicorn workspace107.main:create_app --factory --port "$PORT" --log-level warning &
SERVER_PID=$!

for _ in $(seq 1 50); do
  curl -sf "${BASE}/health" >/dev/null 2>&1 && break
  sleep 0.2
done
curl -sf "${BASE}/health" >/dev/null || { echo "服务没能启动" >&2; exit 1; }

say "1. 取得个人空间"
WORKSPACE_ID=$(api GET /me | jget "['workspaces'][0]['id']")
api PATCH "/workspaces/${WORKSPACE_ID}" \
  -d '{"default_environment_version_id":"ev_python_312"}' >/dev/null
echo "Workspace: $WORKSPACE_ID"

say "2. 创建 Project 并写入代码"
PROJECT_ID=$(api POST "/workspaces/${WORKSPACE_ID}/projects" \
  -d '{"name":"演示项目","description":"端到端闭环演示"}' | jget "['id']")
api PUT "/projects/${PROJECT_ID}/files" -d '{
  "path": "train.py",
  "content": "import json, os, pathlib\npathlib.Path(\"outputs\").mkdir(exist_ok=True)\nepochs = int(os.environ[\"EPOCHS\"])\nfor i in range(1, epochs + 1):\n    print(f\"epoch {i}/{epochs}\", flush=True)\npathlib.Path(\"outputs/metrics.json\").write_text(json.dumps({\"epochs\": epochs, \"accuracy\": 0.93}))\nprint(\"done\")\n"
}' >/dev/null
echo "Project: $PROJECT_ID"

say "3. 保存 Project Version"
VERSION=$(api POST "/projects/${PROJECT_ID}/versions" -d '{"message":"初始版本"}' | jget "['label']")
echo "版本: $VERSION"

say "4. 配置 Workspace Variable 和运行方案"
api PUT "/workspaces/${WORKSPACE_ID}/variables" -d '{"name":"EPOCHS","value":"3"}' >/dev/null
CONFIG_ID=$(api POST "/projects/${PROJECT_ID}/run-configurations" -d '{
  "name": "默认运行",
  "command": "python train.py",
  "compute_plan_id": "plan_cpu_quick",
  "environment_variables": {"EPOCHS": "${{ vars.EPOCHS }}"},
  "artifact_rules": [{"path": "outputs", "name": "训练结果", "optional": false}]
}' | jget "['id']")
echo "运行方案: $CONFIG_ID"

say "5. 提交前检查"
api POST "/projects/${PROJECT_ID}/runs/preflight" -d "{\"run_configuration_id\":\"${CONFIG_ID}\"}" \
  | python3 -m json.tool

say "6. 提交 Run"
RUN_ID=$(api POST "/projects/${PROJECT_ID}/runs" \
  -d "{\"run_configuration_id\":\"${CONFIG_ID}\",\"name\":\"演示运行\"}" | jget "['id']")
echo "Run: $RUN_ID"

say "7. 等待状态流转"
for _ in $(seq 1 100); do
  api POST /runs/sync >/dev/null
  STATUS=$(api GET "/runs/${RUN_ID}" | jget "['run']['status']")
  echo "  状态: $STATUS"
  case "$STATUS" in
    succeeded|failed|cancelled|submit_failed) break ;;
  esac
  sleep 0.3
done

say "8. 执行事件时间线"
api GET "/runs/${RUN_ID}" | python3 -c "
import json, sys
detail = json.load(sys.stdin)
for event in detail['events']:
    print(f\"  {event['created_at'][11:19]}  {event['type']:<20} {event['message']}\")
"

say "9. 日志"
api GET "/runs/${RUN_ID}/logs" | python3 -c "
import json, sys
for chunk in json.load(sys.stdin):
    if chunk['content'].strip():
        print(f\"--- {chunk['stream']} ---\")
        print(chunk['content'].rstrip())
"

say "10. Artifact"
ARTIFACT_ID=$(api GET "/runs/${RUN_ID}" | jget "['artifacts'][0]['id']")
api GET "/artifacts/${ARTIFACT_ID}/files" | python3 -m json.tool
echo "--- metrics.json ---"
curl -sS "${BASE}/artifacts/${ARTIFACT_ID}/download?path=metrics.json" -H "$USER_HEADER"
echo

say "11. 复现快照"
api GET "/runs/${RUN_ID}" | python3 -c "
import json, sys
snapshot = json.load(sys.stdin)['snapshot']
print(f\"  Project Version : {snapshot['project_version_id']}\")
print(f\"  执行命令        : {snapshot['command']}\")
print(f\"  运行环境        : {snapshot['environment_image']}\")
print(f\"  环境变量        : {snapshot['environment_variables']}\")
print(f\"  Secret 引用     : {snapshot['secret_references']}  (只有名称，没有值)\")
print(f\"  调度配置        : {snapshot['scheduler']}\")
"

printf '\n\033[0;32m演示完成。整条核心闭环跑通。\033[0m\n'
