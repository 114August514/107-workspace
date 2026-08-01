# CI 运行时配置

- 状态：已完成
- 认领：August / Codex
- 上下文：PR #2 / Actions run 30693031752
- 开始：2026-08-01 17:28 +0800
- 结束：2026-08-01 17:33 +0800

## 意图

由 GitHub Actions 负责配置 Python、Node 与 Windows 编码，撤掉任务脚本对 `uv` PATH
行为的推断，保持 Makefile 和 Python 任务入口职责单一。

## 预期改动

- `.github/workflows/ci.yml`：显式安装 Python 3.12，并为 Windows job 启用 UTF-8。
- `scripts/tasks/common.py`：删除 PATH 修补逻辑。
- `scripts/tests/test_workspace.py`：删除只服务于该修补逻辑的测试。
- `docs/archive/`：更正首轮 CI 修复记录并归档本轮结果。

## 仓外副作用

推送后触发 PR #2 GitHub Actions；四项检查全绿后 squash merge。

## 回退方式

回退本任务提交；尚未合并前不会影响默认分支。

## 验收

- 工作流脚本测试与 Ruff 通过。
- `make check` 通过。
- PR #2 四项 GitHub Actions 全部通过。

## 禁区

- 不改 `docs/product/design.md` 与 `docs/contributing/git-workflow.md`。
- 不在任务脚本中加入 GitHub Actions 或平台探测逻辑。
- 不加依赖。

## 结果

- 三个 Python job 均通过当前稳定的 `actions/setup-python@v7` 显式安装 Python 3.12；
  `setup-uv` 只负责 uv 与缓存。
- Windows job 通过标准 `PYTHONUTF8=1` 环境启用 UTF-8，保留 seed 工具的中文输出。
- 任务公共层恢复为普通的 PATH 命令解析，不感知 GitHub Actions、Makefile 或平台编码。
- 工作流 YAML 结构解析通过；本地运行时确认 Python 3.12、Node 24 和 UTF-8 中文输出。
- `make check` 全部通过，包括工作流 14 项、后端 102 项、前端 14 项、生产构建和
  OpenAPI 契约；约 1.29 MB 主 chunk 警告按既定范围暂不处理。
- PR run `30694129625` 的 Linux 统一检查、migration 与 Compose 均通过；Windows 也已
  通过完整检查、迁移和 UTF-8 中文输出，最后只在清理仍由 Uvicorn 子进程占用的 SQLite
  文件时失败。进程生命周期修复见
  [`2026-08-01-windows-process-lifecycle.md`](2026-08-01-windows-process-lifecycle.md)。
