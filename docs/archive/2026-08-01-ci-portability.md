# CI 跨平台修复（首轮）

- 状态：已替代
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

- Alembic 配置改用 ASCII 注释，可由 Windows `cp1252` 代码页读取。
- 首轮 PATH 推断通过本地测试，但 PR run `30693031752` 证明它没有覆盖 GitHub Linux
  runner 的实际 Python 目录形态，Node 仍被解析为 22.23.1。
- Windows 已越过 Alembic 读取，随后暴露 `seed.py` 向 cp1252 stdout 输出中文时的
  `UnicodeEncodeError`。
- PATH 推断及其测试已由后续的
  [`2026-08-01-ci-runtime-provisioning.md`](2026-08-01-ci-runtime-provisioning.md) 删除；
  Python 与编码改由 GitHub Actions 配置。
- `docs/product/design.md`、`docs/contributing/git-workflow.md`、业务实现和依赖均未修改。
