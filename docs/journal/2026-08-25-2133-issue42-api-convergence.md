# issue42-api-convergence

- 状态：四项独立 Review findings 已修复并验证，等待 targeted re-review
- 认领：Issue 42 sole writer（worktree `107-workspace-42-api-convergence`）
- 上下文：Issue #42，Parent #34；#35–#41 已合并；起点 `main` / PR #72 `9b00f4b`
- 分支：`refactor/42-api-convergence`
- 开始：2026-08-25 21:33 +0800

## 意图

彻底删除开发期 Workspace ownership 兼容层，使 Home、Activity、Notification、API、OpenAPI、
generated TypeScript、前端路由和 seed/smoke 只表达当前 User / UserGroup / Owner / Visibility /
Initiated User 语义。所有受控消费者在同一候选中 clean cutover，不保留 alias、fallback 或旧 URL。

## 实施计划

1. 盘点 Workspace 表、字段、DTO、route、repository、fixture 与前端消费方，冻结最小当前契约。
2. 先用行为测试补足 Home Owner 投影和 Activity/Notification 非绕过授权；观察有意义的新断言失败。
3. 新增 schema-only cutover migration：FK-safe 清空不兼容业务状态，删除兼容列/表；downgrade 只重建空的 predecessor schema。
4. 收敛 backend domain/application/repository/API，删除 Workspace 模型、routes、helpers 和全部受控调用方。
5. 重新生成 OpenAPI/TypeScript，机械迁移 frontend routes/pages/navigation 与 seed/smoke/fixtures，删除旧兼容测试。
6. focused schema/contract/behavior 验证后运行一次 `make check` 与真实 `make smoke`；自审并修复 material findings。

## 冻结契约

- `/api/v1/me` 返回当前 User、User Groups、当前可见/最近 Projects 与 Runs，以及 User 级 execution context；没有 Personal Workspace 字段。
- User Group 使用 `/api/v1/user-groups` 与 `/user-groups/:userGroupId`；不保留 `/workspaces` 或 `/workspaces/:id`。
- Project/Environment/SharedResource/Grant/Entitlement 使用既有显式 Owner DTO；Run 使用 `initiated_by_user`。
- Activity 仅保留当前授权的 UserGroup / Project 聚合；不提供语义过宽的 `/me/activities`。Notification 按 recipient 授权，且失去/尚无 UserGroup 访问权的邀请与移除通知不带导航 target。
- Migration 允许删除旧开发数据；保留 Users/UserGroups 等当前上游表，且不做旧数据转换。

## 仓外副作用

仅 non-force push 分支并创建 PR；不部署、不访问 live 107、不合并。

## 回退方式

通过后续 revert；migration downgrade 仅恢复空的 predecessor schema shape，不恢复已清理数据。

## 验收

- Focused Home/Owner auth、Activity/Notification authorization、project creation/navigation、migration round-trip、generated contract tests。
- `make check`
- `make smoke`

## 候选结果（2026-08-26）

- `f42a9c7e1d30` 以 schema-only cutover 删除兼容列、私有 migration 表和 `workspaces` 表；迁移 round-trip 通过。
- Backend runtime 不再包含 LegacyWorkspace model/repository/service/routes 或任何 `workspace_id` 字段；Home、Activity、Notification、Project/Fork/Run 均使用当前权威。
- OpenAPI/generated TypeScript/client/frontend routes 已 clean cutover；旧 Personal/Collaborative Workspace 页面、helpers、fixtures 与兼容测试已删除。
- Focused backend：287 passed、3 skipped；frontend：120 passed；`make smoke` 完成真实隔离 HTTP Project → Version → Run → Artifact 闭环。
- 最终 `make check` 仅发现新增测试 import 顺序一项 backend lint；已修复，并用 `ruff check` 与 `ruff format --check` 对该文件确认通过。其余 backend/frontend tests、build、OpenAPI/generated TypeScript 一致性均通过。
- Review remediation：Home `recent_runs` 同时要求当前 Project 可见且 `initiated_by_user_id` 为当前 User；双成员反例通过。删除 `/me/activities` 及其 repository 聚合；邀请/移除通知对无访问权 recipient 明确为非链接；更新 Run Configuration 和当前 resource fixture 术语。
- Remediation focused backend：5 passed；frontend NotificationBell：12 passed，TypeScript typecheck 通过；真实 `make smoke` 再次完成隔离 HTTP 核心闭环。

## 禁区

- 不改 Scheduler / Storage / Worker，不实现 #19/#20/#21 设计重做，不加依赖或框架。
- 不触碰 primary/其他 worktree，不保留 Workspace compatibility。
