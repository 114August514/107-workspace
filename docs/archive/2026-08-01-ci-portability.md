# CI 跨平台修复

- 状态：已完成
- 认领：August / Codex
- 上下文：PR #2 / Actions run 30692294918
- 开始：2026-08-01 16:57 +0800
- 结束：2026-08-01 17:01 +0800

## 意图

修复规范入口在 GitHub Actions 上的两项跨平台失败，同时保持 Node.js 24 与
pnpm 11 的硬门槛。

## 预期改动

- `scripts/tasks/common.py`：恢复 `uv run` 启动前的工具 PATH 优先级。
- `scripts/tests/test_workspace.py`：覆盖重复解释器目录的 PATH 场景。
- `backend/alembic.ini`：避免 Windows 本地代码页读取 UTF-8 注释失败。

## 仓外副作用

修复提交将推送到 PR #2，并触发 Linux 与 Windows GitHub Actions 重跑。

## 回退方式

回退本任务提交；尚未合并前不会影响默认分支。

## 验收

- 工作流单测通过。
- 后端 Ruff 检查通过。
- `make check` 通过。
- PR #2 四项 GitHub Actions 检查通过后再合并。

## 禁区

- 不改 `docs/product/design.md` 与 `docs/contributing/git-workflow.md`。
- 不改业务实现或目标架构口径。
- 不加依赖。

## 结果

- `uv run --no-project` 仅在 Python 目录重复出现在 PATH 首尾时移除新增的首项，恢复调用
  前原有工具优先级；独立的 uv-managed Python 目录保持不变。
- Node.js 版本检查仍严格要求 24.x，pnpm 仍严格要求 11.x。
- Alembic 配置改用 ASCII 注释，可由 Windows `cp1252` 代码页读取。
- 工作流 15 项、后端 102 项、前端 14 项、前端构建与 OpenAPI 合同均通过；构建仍有
  已知的约 1.29 MB 主 chunk 警告，本任务不处理分包设计。
- `docs/product/design.md`、`docs/contributing/git-workflow.md`、业务实现和依赖均未修改。
