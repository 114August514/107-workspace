# issue-37-config-scopes

- 状态：进行中
- 认领：August / Codex
- 上下文：Issue #37；分支 `refactor/37-config-scopes`；linked worktree `/home/august/Projects/ustc_107/107-workspace-37`
- 开始：2026-08-21 11:32 +0800

## 意图
- 为 Issue #37 建立 User / User Group / Project Variable 与 Secret scope。
- 支持标准 `${{ vars.NAME }}` / `${{ secrets.NAME }}` 的 Project → exact Project Owner 解析，以及仅查 Initiated By User 的 `${{ user.vars.NAME }}` / `${{ user.secrets.NAME }}`。
- 保持 Variable 在 Run Snapshot 中固定值、Secret 仅固定 exact reference 并在执行时重新校验；Secret 明文不得进入普通 API、Snapshot、日志或 UI。

## 协调与依赖
- 依赖私有 Issue #36 提供 Project Ownership / Visibility contract；不得绕过 User / User Group exact owner 语义。
- 与 active #38（User Resource Entitlement）和 #39（Asset Ownership）协调，避免覆盖 ownership/access、run/config、repository/table、seed 与 OpenAPI 改动。
- Run convergence #41 需要消费本 Issue 的稳定 config resolution contract。

## 实现进度
- 已完成当前持久化基础切片：ConfigScope/SecretReference、scoped Variable/Secret 表与迁移、Repository/SecretVault scope API、legacy workspace service 显式映射。
- Commit：`5b205f3`；目标分支仍在进行中。

## API 切片
- 新增 `ConfigurationService` 与 scoped Variable/Secret CRUD 路由，User/User Group/Project 均通过同一授权入口；PUBLIC Project 不绕过 Project guard。
- 已通过 canonical contract sync/check，生成 OpenAPI 与 frontend types。
- 当前仍不接入 Run resolver/execution；待补 repository/migration integration fixtures 与完整 auth behavior tests。
- 待后续切片：Run resolution/Secret exact-ref 调用方、迁移集成测试与完整 repository/auth 行为测试。

## 授权与契约决策
- User Group 配置权限使用私有 `AccessGuard.scoped_config_group`：repository-filtered active membership 后按内部 `capabilities_of(role)` 检查 CONFIG_VIEW/CONFIG_MANAGE，不改变 `UserGroupOut` capability matrix。
- 公共路径固定为 `/users/{user_id}`, `/user-groups/{user_group_id}`, `/projects/{project_id}` 下的 `variables`/`secrets`，不暴露 generic scope discriminator。
- Secret 路径只返回名称，OpenAPI contract test 确认无 plaintext `value` 字段。
- Commit：`f1c0f99`；Run resolver/execution integration 仍待后续切片。

## 仓外副作用
无；不进行 live 107 活动、远端发布或其他仓外操作。


## 集成证据更新
- 真实 SQLite persistence tests：2 passed；真实 HTTP explicit resource CRUD/auth tests：2 passed；existing #35 Alembic round-trip migration test：1 passed。
- HTTP coverage now initializes actual User identity, creates actual UserGroup and Project, exercises set/list/delete for Variable and Secret in all three families, foreign User and existing Project unauthorized 404, and asserts Secret list has no plaintext/value.
- Standard `main.py` import and single `app.include_router(api_router)` wiring restored; no special-case router registration or dependency-bound changes.

## 集成证据更新
- SQLite persistence：2 passed；HTTP explicit User/UserGroup/Project CRUD：2 passed；existing HTTP `/api/v1/me` test：1 passed。
- #35 migration fixture now includes personal/collaborative Variable and Secret rows and asserts exact `user`/`user_group` scopes; upgrade/downgrade/upgrade test passes.
- FastAPI diagnostic confirmed unchanged `/api/v1/me` works; prior config 404 was username-vs-ID test setup, not router/dependency breakage. No dependency bounds or main wiring workaround changed.
- Commit：`30eb602`。
## 回退方式
`git revert <commit>`

## 验收
- User、User Group、Project 三种 scope 的 CRUD、repository 与 authorization 测试。
- 标准/显式 user 引用解析、Project → exact Project Owner 优先级、命中后不可回退、缺失/无权/不可用引用使 preflight 失败。
- Variable Snapshot 固定值、Secret exact reference 与执行时授权校验、Secret 脱敏和不可回读。
- Fork 复制表达式但不复制值或访问权；迁移拒绝无法证明 owner 的 legacy Workspace config。
- `make check`

## 禁区
- 不动 primary dirty worktree 的现有修改。
- 不修改 #36/#38/#39 的 ownership、entitlement 或 asset worktree 内容。
- 不加依赖；不实现通用 key-value framework。
