# Windows 服务进程生命周期

- 状态：已完成
- 认领：August / Codex
- 上下文：PR #2 / Actions run 30694129625
- 开始：2026-08-01 17:55 +0800
- 结束：2026-08-01 17:58 +0800

## 意图

让 Linux 与 Windows 都直接持有实际 Uvicorn 进程，停止并等待服务退出后再清理临时
SQLite 数据库，避免 uv 包装进程退出后遗留子进程。

## 预期改动

- `scripts/tasks/project.py`：由 uv 查询项目解释器，再直接启动长期后端进程。
- `scripts/tests/test_workspace.py`：验证解释器解析不依赖平台目录结构。
- `docs/archive/`：归档本轮 CI 修复结果。

## 仓外副作用

推送后触发 PR #2 GitHub Actions；四项检查全绿后 squash merge。

## 回退方式

回退本任务提交；尚未合并前不会影响默认分支。

## 验收

- 新增测试先失败、实现后通过。
- `make smoke` 与 `make check` 通过。
- PR #2 四项 GitHub Actions 全部通过。

## 禁区

- 不改 `docs/product/design.md` 与 `docs/contributing/git-workflow.md`。
- 不按平台硬编码虚拟环境目录。
- 不忽略临时目录清理错误或遗留后台进程。
- 不加依赖。

## 结果

- uv 在 `backend/` 项目中返回实际 Python 路径，不需要判断 `.venv/bin` 或
  `.venv\Scripts`，Linux 与 Windows 使用同一实现。
- backend dev 与 smoke 都直接运行 `Python -m uvicorn`；`Popen` 不再只持有 uv 包装
  进程，停止等待完成后才离开临时目录。
- 解释器解析测试按计划先因函数不存在而失败，接入实现后通过。
- `make smoke` 完成迁移、seed、HTTP 核心 Run、日志与 Artifact 闭环，并正常清理目录。
- `make check` 全部通过，包括工作流 15 项、后端 102 项、前端 14 项、生产构建与
  OpenAPI 契约；约 1.29 MB 主 chunk 警告按既定范围暂不处理。
- PR CI 是合并前对 Windows 文件锁释放行为的最终验收门槛。
