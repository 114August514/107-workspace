# issue40-cross-owner-use-grant
- 状态：实现完成，`make check backend` + contract check 通过
- 认领：zxb3；本 worktree 的 sole writer
- 写入边界：`/home/zxbq/107-workspace`（分支 `feat/40-cross-owner-use-grant`）
- 分支：`feat/40-cross-owner-use-grant`
- 起点：`origin/main` `23bffe2`（#35 PR #57、#39 PR #58 已合并；依赖 #35/#39 均已 closed）
- 开始：2026-08-21 15:58 +0800
- 关联：Issue #40；Parent #34；Depends on #35（已合并）、#39（已合并）

## 意图与完成边界

在 #39 已建立的 `application/asset_use.py` exact-same-Owner use boundary 上扩展「或存在有效 USE Grant」，
实现跨 Owner Environment / Shared Resource 的统一 USE Grant 模型，使资产 Ownership 与使用资格明确分离。

Grant 语义（来自 `docs/product/design.md` GR-401 ~ GR-404）：

- `Grantee = User | User Group`；`Action = USE`；`Target = Environment | Shared Resource`（顶层资产）。
- Grant 作用于顶层资产，不直接授予某个 Version；Run Configuration / Run Snapshot 仍引用确定 Version。
- Grant 不授予资产管理、发布、归档、转移等生命周期权限，也不创建 Membership。
- User Group 作为 Grantee 时，具体 User 必须同时具有该组有效 Membership 才能以该组资格使用资产。
- Owner scope 内使用自身资产无需额外 Grant；跨 Owner 使用必须存在有效 USE Grant。
- Ownership 转移后原 Owner 建立的 Grant 失效。
- Grant 撤销不改写既有 Run Snapshot，但后续创建/重新执行/重新物化需按当前规则重新校验。

本工作单元包含：Grant 领域对象与值对象、数据库表与 repository、最小 application service / API contract
（创建、查看、撤销）、`asset_use.py` 上的 USE Grant 扩展、Run / preflight 的跨 Owner 使用资格查询，
以及覆盖 User→Asset、UserGroup→Asset、target/action 约束、Membership 借用、Ownership 转移失效的授权测试。

## 冻结契约（初稿，实现前可微调）

- 新增 `grants` 表：`grantee_kind`（user / user_group）、`grantee_id`、`target_kind`（environment / shared_resource）、
  `target_id`、`action`（当前仅 `use`）、`granted_by_id`、`created_at`。Target 仅允许 Environment / Shared Resource，
  Action 仅允许 USE；不引入有效期、复杂 Action 集合或 Project-level Grant。
- USE Grant 不创建 Membership，不扩大资产管理权限；Grant 是独立关系对象，按当前 Owner 边界授权（GR-401）。
- `asset_use.py` 的 use boundary 扩展为「consuming Project Owner 与 asset Owner 完全相等 **或** 存在以
  发起 User（含其有效 Membership 的 User Group）为 Grantee 的有效 USE Grant」；repository actor discovery
  与 exact snapshot lookup 职责不变。
- Ownership 转移后旧 Grant 失效：Grant 不随 Owner 变更改写，但 use authorization 在转移后对旧 Grant 一律 fail closed。
- Grant 撤销不改写既有 Run Snapshot；后续创建/重新执行/重新物化按当前有效 Grant 重新校验。

## 已接受风险与非目标

- 非目标：Grant 有效期、复杂 Action 集合、Project-level Grant、完整授权管理 UI、通用 ACL / policy engine、
  改变 Version 不可变与 Input Binding 精确引用语义。
- 风险控制：Grant 只扩展 use boundary，不引入新资产管理能力；User Group Grant 必须与有效 Membership 叠加校验。

## 验证计划

1. User→Asset、UserGroup→Asset 的 USE Grant 创建/查看/撤销，含授权测试。
2. Grant target 仅允许 Environment / Shared Resource；Action 仅允许 USE；不允许 Version / Project。
3. Owner scope 内无需 Grant；跨 Owner 无有效 Grant 时 fail closed；有有效 Grant 时通过。
4. User Group Grant 不能被非该组有效成员借用。
5. Ownership 转移后旧 Grant 不生效。
6. 受影响的 migration / authorization / API tests 与 `make check` 通过。

## 仓外副作用

无；只使用隔离临时 SQLite / test storage。

## 实现完成（2026-08-22）

### 已实现

- **Domain** (`domain/grant.py`): `Grant` 聚合、`GrantAction.USE`、`GrantTargetKind.ENVIRONMENT/SHARED_RESOURCE`；`ids.GRANT="gnt"` 前缀；`ActivityAction.GRANT_CREATED/GRANT_REVOKED`、`TargetType.GRANT` 枚举值。
- **Migration** (`1f61cd1dc3ac_grants.py`): `grants` 表，`uq_grant_grantee_target_action` 唯一约束，`ix_grants_target`/`ix_grants_grantee` 索引，`granted_by_id` FK→`users.id` (RESTRICT)。无 target FK（Grant 可引用已删除资产）。
- **Repository**: `GrantRepository` port + `GrantRepositoryImpl`（`add`/`get`/`list_for_target`/`list_for_grantee`/`delete`/`exists_use_grant`）；`EnvironmentRepository.get_by_id`/`get_version_by_id`、`SharedResourceRepository.get_by_id` trusted lookups。
- **AssetUse** (`application/asset_use.py`): 双路径授权——same-owner discovery (Issue #39) + Grant 路径。Grant 路径检查 `target_owner`（Project Owner）或 acting `user_id`（User-level Grant）的 USE Grant。
- **Service+API**: `GrantService`（create/list_for_target/revoke）；`AccessGuard.environment()`；`POST/GET/DELETE /api/v1/grants` 路由；`GrantOut`/`GrantCreateIn` schemas；`grant_out` presenter；`Services.grants` 注入。
- **Contract**: `contracts/openapi.json` + `frontend/src/api/schema.d.ts` 已重新生成。
- **Tests**: `test_cross_owner_use_grant.py`（7 个行为测试）+ `test_grants_migration.py`（迁移 round-trip 测试）全部通过；`test_asset_owner_use.py`（Issue #39 回归）全部通过。

### 修复的遗留问题

- 恢复 `ids.SHARED_RESOURCE_VERSION`（被前序编辑误删）。
- 恢复 `repositories.py` 的 `ComputePlan` import（被前序编辑误替换）。
- 恢复 `schemas.SharedResourceUpdateIn.description` 字段（被前序编辑误删）。

### 验证结果

- `make check backend`：lint + format + 221 tests passed（2 skipped）。
- Contract check：OpenAPI 与 frontend types 匹配。
