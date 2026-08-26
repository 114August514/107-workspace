# environment-core

- 状态：进行中
- 认领：August
- 上下文：Issue #45；worktree `/home/august/Projects/ustc_107/107-workspace-45`；branch `feat/45-environment-core`
- 开始：2026-08-26 23:43 +0800

## 意图
交付 Issue #45 的 Environment Core 用户表面：浏览可用 Environment 及确定版本，在
User Group 维护默认版本，在 Run Configuration 保存 exact Environment Version，并在
发起 Run 前展示后端判定的使用资格与可用性。

## 预期改动
- `backend/`：补足 Environment 查询、默认版本和 Run Configuration/preflight 契约。
- `contracts/`：由后端生成 OpenAPI 与前端 TypeScript 类型。
- `frontend/`：新增 Primer Environment 页面并接入 User Group、Run Configuration。

## 仓外副作用
GitHub Issue #45 的实现分支将推送到远端并创建 PR；撤销方式为关闭 PR、删除远端短期分支。

## 回退方式
未推送前删除 linked worktree 和本地短期分支；提交后使用 `git revert <commit>`。

## 验收
- Issue #45 每条验收条件有 fresh evidence。
- 前端测试、生产构建与 `make check` 通过。
- 浏览器覆盖桌面、375px、键盘路径以及 loading/empty/error。

## 禁区
- 不实现 Environment 构建、发布、归档或 Ownership 转移。
- 不实现搜索、筛选、推荐、版本差异或 Grant 管理 UI。
- 不新增依赖或前端推导权限。

## 当前状态（2026-08-27）
- 候选提交：`6738c74`、`a35a47b`、`d74698b`。
- 后端：Owner/active User Group/USE Grant 可用环境查询、环境与版本详情、User Group
  exact default、Project 环境选择、不可用版本保存拒绝、可回退 migration 已完成。
- 前端：Environment 列表/详情/版本、User Group 默认版本、Run Configuration exact
  版本及 preflight 状态已完成；权限与可用性只消费后端 contract。
- 浏览器：1440px、375px、键盘焦点/Enter、loading/empty/error、默认版本保存、
  Run Configuration 重开与 preflight exact version 均已实测。
- 验证：`make check` 通过；backend targeted 6 passed；frontend targeted 11 passed；
  production build 通过。独立 reviewer 结论 `PASS`。
- PR：[#80](https://github.com/114August514/107-workspace/pull/80)；等待托管检查与评审。
