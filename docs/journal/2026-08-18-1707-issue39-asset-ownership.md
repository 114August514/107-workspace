# issue39-asset-ownership

- 状态：待 PR review（C2；independent review remediation 的 targeted re-review PASS；合并前保持 active）
- 认领：August；当前 worktree 的 sole writer
- 写入边界：`/home/august/Projects/ustc_107/107-workspace-39-asset-ownership`
- 分支：`refactor/39-asset-ownership`
- 起点：`origin/main` `bbe43fd13a293d35e5f50e968bcd2662e7d4a57d`
- 开始：2026-08-18 17:07 +0800
- 关联：Issue #39；依赖已合并 Issue #35 的 `OwnerReference`、UserGroup 与唯一有效 Owner 不变量

## 意图与完成边界

将 Environment / Shared Resource ownership 从 legacy Workspace / Platform-null 语义干净迁移为现有 `OwnerReference` 的两个合法主体：User 或 UserGroup。发现必须在 repository 查询中按当前 User owner或目标 UserGroup 的 active Membership 过滤；跨 owner 对象按不存在处理。#40 才增加有效 USE Grant，#39 不保留 all-authenticated catalog compatibility。

本工作单元包含数据库破坏性迁移、领域/仓储/应用/API clean cutover、dev/demo bootstrap、OpenAPI 与生成的前端类型、受影响调用方，以及覆盖迁移、越权、契约和 seed 生命周期的永久测试。当前候选已实现并完成本地验证；PostgreSQL 仍是明确未验证范围。

## 冻结契约

### 数据库与领域

- `environments`、`shared_resources` 各使用两个 nullable FK：`owner_user_id -> users.id ON DELETE RESTRICT`、`owner_user_group_id -> user_groups.id ON DELETE RESTRICT`。
- 两表各有 named exactly-one CHECK：两个 owner 列必须且只能有一个非 NULL；两个 owner 列分别建索引。
- 仓储映射到现有 `OwnerReference(OwnerKind.USER | OwnerKind.USER_GROUP, id)`；不引入 generic Asset table、Platform owner 或 NULL owner。
- EnvironmentVersion、SharedResourceVersion、SharedResourceVersionFile 不重复 owner，沿父聚合继承发现边界。
- User-facing list/get/version/file 查询在 repository SQL 中过滤：User owner等于 actor，或 owning UserGroup 存在该 actor 的 active Membership。Invited、left、removed、无 Membership 均不可发现。可信的已固定 Run Snapshot 执行读取若必须保留 unscoped lookup，方法名必须显式为 internal/by-id，不能被 public service 直接使用。

### API Owner DTO

最终选择 `OwnerSummaryOut`，字段仅为 `kind`、`id`、`display_name`。`display_name` 是为当前 UI owner 标签提供的显式 summary projection：User 取 `User.display_name`，UserGroup 取 `UserGroup.name`；它不是 identity，也不进入领域 `OwnerReference`。列表实现必须 join/batch resolve，禁止 presenter 循环 N+1。

`EnvironmentOut.owner` 与 `SharedResourceOut.owner` 使用 `OwnerSummaryOut`。canonical schema 中删除 `owner_workspace_id`、`is_platform_owned`，`OwnerKind` 只有 `user`、`user_group`。旧 Workspace Shared Resource routes 只可作为已标 deprecated 的 bounded route adapter，返回 canonical owner DTO；adapter 不把 Workspace owner 语义带回 domain/repository。不提供 public compatibility field 或 all-authenticated Platform catalog read。

### 破坏性迁移与 rollback truth

- 新迁移以当前唯一 head `e35a1d7c9b20` 为 predecessor，预留 revision `c471ac39f002`。
- Upgrade 按 child-first 删除 legacy aggregate DB rows：`shared_resource_version_files` → `shared_resource_versions` → `shared_resources`，以及 `environment_versions` → `environments`；随后建立空的 owner-constrained schema。
- 1B 已明确允许这些 legacy Environment / Shared Resource DB aggregates 丢弃。迁移不读取、删除或 GC content-addressed blob storage。
- `workspaces.default_environment_version_id`、`projects.environment_version_id`、`run_configurations.environment_version_id`、`run_configurations.input_bindings` JSON、`run_snapshots.payload` JSON 都是无 FK 的 exact references。迁移保持其字节/JSON 语义不变；对应旧 asset/version 删除后它们必须保持 unavailable，不能重写到 default/latest。
- 新 demo Environment/Version 必须使用新 ID：`env_platform_python_base_2026`、`env_platform_pytorch_2026`、`ev_platform_python_312_2026`、`ev_platform_pytorch_24_2026`。绝不复用被删除的 `env_python_base`、`env_pytorch`、`ev_python_312`、`ev_pytorch_24`，否则历史 exact reference 会静默改指新内容。
- Downgrade 明确非无损：先 child-first 删除新 schema 中全部 asset aggregate rows，再恢复空的旧 schema。它不能恢复 upgrade 删除的 legacy rows；external exact refs 仍原样悬空；blob 仍不触碰。
- 因此回退不等于 `git revert`。代码回退需配套 Alembic downgrade；数据恢复只能来自迁移前数据库备份，或按新 ID 重新 seed（后者不是历史数据恢复）。若没有备份，旧 aggregate 元数据不可恢复。

### Seed / bootstrap

- 非 demo `seed_catalog` 只幂等创建 ComputePlans，不创建 platform asset group、Environment 或 Shared Resource。
- `python -m workspace107.tools.seed --demo --platform-owner-username <username>` / 既有 `WORKSPACE107_SEED_DEMO=true` 才确保 dedicated ordinary UserGroup `grp_platform_assets` 与 demo platform Environments/Versions。CLI 参数默认 `student`；local-demo 可选环境变量为 `WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME`。
- `--platform-owner-username` / `WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME` 仅在 group 首次不存在时选择真实自然人 initial Owner，属于 dev/demo bootstrap input，不是 production provisioning 或持续配置 authority。
- group 已存在时 persisted Membership 是唯一持续 authority。后续正常 transfer 后 rerun seed 必须保留新 Owner，不可按 CLI/env 把 Owner 改回初始值；输入与当前 Owner 不同不是 drift/error。
- 固定 seed ID 已存在但 owner 或 immutable version content 不一致时 fail closed；不静默改 owner/content。

## Consumers / 预期改动

- Migration/schema：`backend/migrations/versions/c471ac39f002_asset_ownership.py`、`backend/src/workspace107/infrastructure/db/tables.py`。
- Domain/ports/repositories：`backend/src/workspace107/domain/models.py`、`backend/src/workspace107/domain/ports/repositories.py`、`backend/src/workspace107/infrastructure/db/repositories.py`，复用 `domain/ownership.py`。
- Application authorization/callers：`application/access.py`、`catalog_service.py`、`shared_resource_service.py`，以及 Project / Run Configuration / Run / legacy Workspace 中所有 user-facing EnvironmentVersion、SharedResourceVersion lookup callers。
- API：`api/schemas.py`、`api/presenters.py`、`api/routes/catalog.py`、`api/routes/shared_resources.py`；旧 Workspace routes 仅作 bounded deprecated adapters。
- Seed/runtime：`backend/src/workspace107/tools/seed.py` 提供 dev-only `--platform-owner-username` 与 local-demo `WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME`；二者只在 first bootstrap 生效。
- Contract/frontend：生成的 `contracts/openapi.json`、`frontend/src/api/schema.d.ts`，以及受 owner shape 影响的 `frontend/src/api/types.ts` / client consumers。不得手改生成物来掩盖 backend schema drift。
- Tests：新增 migration、repository discovery、API/OpenAPI、seed lifecycle tests；随后 clean cutover 旧 Platform/null assertions，避免同一契约跨层重复穷举。
- 外部/in-flight：PR #15/#5 需在自身分支消费 canonical owner DTO；本 worktree 不写它、不保留 legacy owner fields 迁就它。

## 已接受风险与非目标

已接受：legacy asset aggregate 元数据不可逆删除；existing config/snapshot exact refs 悬空且不可用；downgrade 只恢复 empty old schema；非 demo 环境首次没有 platform assets。

风险控制：exact refs 不改写；new seed IDs；repository-scoped concealment；owner label 批量解析；SQLite 迁移 up/down/up；正常 UserGroup transfer 后 seed 不 reconcile。PostgreSQL targeted migration evidence 仍待具备对应服务的环境执行。

明确非目标：USE Grants（#40）、production provisioning CLI、break-glass/unavailable-owner recovery、Environment build pipeline（#46）、public Gallery/Visibility、nested resources、asset-specific transfer 或 transfer UI、external IdP sync、generic Asset/ACL framework、live 107 操作。

## 验证计划

1. RED：targeted migration test 从 populated `e35a1d7c9b20` 执行 up/down/up，核对 destructive truth、schema constraints、dangling refs 与 blob sentinel。
2. RED：repository integration test 同时覆盖 Environment / SharedResource 的 User owner、active group member、invited/left/nonmember concealment和 cross-owner get。
3. RED：OpenAPI + existing deprecated adapter test 固定 `OwnerSummaryOut` 及 forbidden fields。
4. RED：seed test 固定 non-demo empty assets、demo real `student` Owner/new IDs、transfer 后 rerun preservation。
5. 实现后逐组转 GREEN；随后运行 PostgreSQL targeted migration/constraint tests、contract regeneration/check、backend check 与项目 `make check`。Web UI 若本 Issue 实际改可见 surface，再用浏览器验证；否则不把生成类型变化冒充 UI 验证。

## Writer ownership / 禁区

- 本 worktree 只有当前 Agent 写入；不委派、不并发修改同一文件。
- 不动 primary `/home/august/Projects/ustc_107/107-workspace` 或任何其他 linked worktree。
- package 1–3 已在此 sole-writer worktree 整合；不再按历史 package 边界保留半新半旧状态。
- 不 commit、push、写 GitHub、访问 live 107、增加依赖或执行 destructive Git 操作。

## 仓外副作用

无；只使用隔离 worktree 内临时 SQLite / test storage。

## 2026-08-18 RED evidence

只运行新增/变更测试；均已正常 collection，并在缺失 #39 production behavior 处失败：

- `cd backend && uv run pytest -q tests/integration/db/test_asset_ownership_migration.py` → `1 failed`：Alembic 无法解析预留 revision `c471ac39f002`，证明 production migration 尚不存在；predecessor populated fixture 已成功建立。
- `cd backend && uv run pytest -q tests/integration/db/test_asset_owner_discovery.py` → `1 failed`：`EnvironmentRow` 不接受 `owner_user_id`，证明新 owner schema/mapping 尚不存在；User/UserGroup/Membership fixture 已成功 flush。
- `cd backend && uv run pytest -q tests/contract/test_asset_owner_contract.py` → `2 failed`：OpenAPI 无 `OwnerSummaryOut`，deprecated Workspace adapter response 无 `owner`。
- `cd backend && uv run pytest -q tests/integration/test_seed.py` → `2 failed, 1 passed`：non-demo seed 仍创建两个 legacy Environments；demo seed 未创建 `grp_platform_assets`。既有 Issue #35 seed test 保持通过。

这些失败均对应冻结的 #39 observable contract，不是 syntax、collection 或 fixture setup 错误。调查未发现推翻计划的 schema/reference 事实：五处 external references 确为无 FK 的 string/JSON；迁移可删除 asset rows 而保持 exact payload 原样。PostgreSQL migration/constraint、完整旧测试 clean cutover、OpenAPI/frontend generation 和 UI surface 尚未验证，留待 production package 后执行。

## 2026-08-18 production package 1

### Actual changes

- 新增 `backend/migrations/versions/c471ac39f002_asset_ownership.py`：upgrade/downgrade 都显式确保 SQLite FK enforcement；五张 asset aggregate 表 child-first 清空；两张父表 batch 重建为 named User/UserGroup FK + exactly-one CHECK + indexes；downgrade 只恢复 empty legacy schema。
- 更新 `infrastructure/db/tables.py`、`domain/models.py`、`domain/ports/repositories.py`、`infrastructure/db/repositories.py`：required `OwnerReference`、portable ORM constraints、owner row mapping、User owner或 exact active Membership SQL predicate、parent-joined Environment/SharedResource version discovery。只有 Shared Resource Snapshot materialization 保留显式 `get_version_by_id` trusted exact lookup。
- 为消除 public service 的 ambiguous raw lookup，机械迁移 `application/access.py`、`catalog_service.py`、`project_service.py`、`workspace_service.py`、`run_configuration_service.py`、`run_service.py`、`shared_resource_service.py` 及 `api/routes/catalog.py` 的 repository calls。Run preflight/rerun 使用 scoped version lookup；已通过 preflight 固定的 materialization 才使用 trusted by-id。
- Repository test 改用独立空 SQLite schema，不借用尚未迁移的 `seed_catalog` fixture；增加 removed Membership concealment，并以 hidden parent version + hydrated visible file 最小证明 version/file 不能绕过父资源发现边界。
- Human correction 已固化：后续 seed package 提供 dev-only `--platform-owner-username`（默认 `student`）与可选 `WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME`；仅 first bootstrap 生效，persisted Owner 转让后不 reconcile。

### Evidence

- `cd backend && uv run pytest -q tests/integration/db/test_asset_ownership_migration.py tests/integration/db/test_asset_owner_discovery.py` → `2 passed`。
- `cd backend && uv run pytest -q tests/integration/db/test_user_group_migration.py` → `1 passed`，证明新增 head 未破坏既有 UserGroup migration round trip。
- `cd backend && uv run ruff check <15 package-1 Python paths>` → `All checks passed`（此前对同一 bounded path set 执行 formatter/import fix）。
- `cd backend && uv run pytest -q tests/unit/domain/test_shared_resource.py` → `2 failed, 7 passed`，两个失败均为待 clean cutover 的旧契约：一个构造器未提供 required owner，一个仍断言 `owner_workspace_id=None` / `is_platform_owned`。未弱化或兼容旧 Platform/null 语义。

### Deviations / remaining boundaries

SQLite FK 由 `migrations/env.py` 的 connect event 在 Alembic transaction 前启用；revision 只 fail-closed 断言 enforcement 已开启。Expected integrity failures 用 SAVEPOINT 隔离；两张 asset 父表都行为性拒绝 both/neither owner，同时各有合法 exactly-one row。PostgreSQL targeted migration evidence仍未执行。

## 2026-08-18 production package 2 + 3 / integrated candidate

### Actual changes

- API clean cutover：`EnvironmentOut`、`SharedResourceOut` / detail 只返回 `OwnerSummaryOut(kind,id,display_name)`；canonical `POST /api/v1/shared-resources` 接受显式 User/UserGroup owner，canonical GET/list 与 Environment catalog 走 repository-scoped discovery。User-owned Shared Resource 不再伪造 Workspace activity feed；UserGroup-owned 操作仍写 UserGroup activity。
- 最小新增 API evidence：同一个 canonical POST/GET 测试覆盖 self User owner、authorized UserGroup owner及一次跨 User owner 404；一个 Environment catalog 测试覆盖两种合法 owner projection。既有 repository membership-state matrix 未复制到 API 层。
- Seed lifecycle：非 demo `seed_catalog` 只创建 Compute Plans；demo 支持 `--platform-owner-username` > `WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME` > `student`。选择只在 `grp_platform_assets` 不存在时解析和创建真实 User；组已存在时不创建新配置 User、不 reconcile 已转让 Owner。
- 两条平台 Environment 与两条 Version 使用全新固定 ID。每条已存在记录必须与 owner 和全部固定内容精确一致；缺失 parent/version 按依赖顺序补齐；冲突记录抛出可见错误且不改写。演示 Project 另用 `grp_demo` 持有的 `env_demo_python_2026`，不冒充平台资产。
- `.env.example`、`deploy/compose.yaml`、`backend/README.md`、`docs/operations/deployment.md` 与 seed CLI/output 已更新为上述本地/demo 真相；Compose 显式把 Owner 输入传给 seed entrypoint，该设置没有进入 production `Settings`。
- 用 canonical repository command `make contract` 重新生成 `contracts/openapi.json` 和 `frontend/src/api/schema.d.ts`；active frontend source 没有 legacy owner consumer，无需手改 consumer。生成物已无 `owner_workspace_id` / `is_platform_owned`。
- Deprecated adapter removal path：#5/PR15 改用 `GET/POST /api/v1/shared-resources` 与 canonical generated owner DTO 后，删除 Workspace GET/POST adapter、deprecated catalog alias、`SharedResourceCreateIn` adapter payload、`list_for_workspace` / `create_for_workspace` / `list_actor_discoverable`、`_legacy_owner` 及对应 adapter contract test；不把 adapter 延伸到新功能。

### Fresh evidence

- `cd backend && uv run pytest -q tests/integration/test_seed.py tests/contract/test_asset_owner_contract.py tests/integration/db/test_asset_ownership_migration.py tests/integration/db/test_asset_owner_discovery.py tests/integration/resource/test_shared_resource_service.py tests/integration/resource/test_platform_shared_resource_input.py tests/unit/domain/test_shared_resource.py` → `40 passed in 5.27s`。
- `make contract` → 成功生成两个正式 artifact；`make contract-check` → `ok OpenAPI and frontend types match the backend`。
- `cd frontend && pnpm run typecheck` → `tsc --noEmit`, exit 0。
- `cd backend && uv run pytest -q` → `207 passed, 2 skipped in 10.67s`。
- `make check` → exit 0：workflow `15 tests`；backend `207 passed, 2 skipped`；frontend `12 files / 48 tests`、typecheck、lint、format、build均通过；API contract check 通过。Frontend 仍输出既有 jsdom `getComputedStyle` 与 bundle-size warnings，但不影响退出状态。
- `POSTGRES_PASSWORD=<local-check-only> make compose-config` → exit 0，渲染出的 API environment 含 `WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME=student`。

### Remaining unverified / review handoff

- PostgreSQL 17 disposable round trip 已补齐，见下节；未访问 live 107，未执行部署或 production provisioning。
- 没有可见 UI 组件改动；前端变化仅来自生成类型，因而没有把浏览器视觉检查冒充本 Issue evidence。
- 本地候选已满足 targeted independent re-review entry；重点仅需重审 personal adapter Activity scope、移除 unscoped repository method 及受其影响的 evidence。

## 2026-08-18 independent review remediation

### Findings and bounded remediation

- IMPORTANT 1：deprecated personal-Workspace create adapter 曾把 legacy personal Workspace ID 作为 Activity scope 传入 `_create_with_owner`，为 User-owned asset 生成伪 Workspace Activity。已删除整个 override seam；create/update/publish 现在都只由 exact `OwnerReference` 决定 Activity scope：User owner 不记录，UserGroup owner 只记录到 owner UserGroup ID。将一条既有 adapter contract test 改为 personal adapter 行为断言，覆盖 canonical User owner projection 与该 legacy Workspace 下零 Activity；既有 group activity test 继续覆盖 exact group scope。
- IMPORTANT 2：删除无调用方、无 actor scope 的 `SharedResourceRepository.latest_version(resource_id)` protocol 和 SQL implementation；保留 actor-scoped version reads 与 fixed-snapshot materialization 专用 `get_version_by_id`。全仓 caller search 无 `latest_version(` 残留，未新增静态源码测试。

### Remediation evidence

- RED：修复前运行 `cd backend && uv run pytest -q tests/contract/test_asset_owner_contract.py::test_issue_39_deprecated_workspace_adapter_maps_personal_owner_without_activity` → `1 failed`，确实观测到 personal legacy Workspace 下多出一条 Activity。
- `cd backend && uv run ruff check src/workspace107/application/shared_resource_service.py src/workspace107/domain/ports/repositories.py src/workspace107/infrastructure/db/repositories.py tests/contract/test_asset_owner_contract.py` → `All checks passed`。
- `cd backend && uv run pytest -q tests/contract/test_asset_owner_contract.py tests/integration/db/test_asset_owner_discovery.py tests/integration/resource/test_shared_resource_input_binding.py tests/integration/resource/test_shared_resource_service.py tests/integration/resource/test_shared_resource_subpath.py` → `35 passed in 8.19s`。
- `make typecheck` → frontend `tsc --noEmit`, exit 0；backend 当前没有配置 type checker，完整 backend lint/build/test 由 `make check` 覆盖。
- `make contract-check` → `ok OpenAPI and frontend types match the backend`。
- `make check` → exit 0：workflow `15 tests`；backend ruff、format（`122 files`）、build 与 `207 passed, 2 skipped`；frontend format/lint/typecheck/build 与 `12 files / 48 tests`；contract check 全部通过。既有 jsdom / antd / bundle-size warnings 仍为非失败输出。

### PostgreSQL 17 disposable evidence

- 唯一 Compose project：`w107i39pg2dcf53f979`；唯一 volume：`w107i39pg2dcf53f979_db-data`；临时 override：`/tmp/w107i39pg2dcf53f979-compose.override.yaml`，只为该 DB 映射随机 localhost port `32768`。使用本机既有 `postgres:17-alpine` image；未启动 api/web，未接触其他 project/volume。
- `docker compose --project-directory <worktree> --project-name w107i39pg2dcf53f979 -f deploy/compose.yaml -f <unique-override> up -d --wait db` → DB healthy；`WORKSPACE107_DATABASE_URL=postgresql+asyncpg://...@127.0.0.1:32768/workspace107 uv run alembic upgrade e35a1d7c9b20` → PostgreSQL transactional DDL，成功到 predecessor。
- 用 `docker compose ... exec -T db psql -v ON_ERROR_STOP=1 -c <legacy-fixture-sql>` 插入最小 legacy Environment+Version 与 SharedResource+Version+File；upgrade 前五张表 count 均为 `1`。`uv run alembic upgrade c471ac39f002` 后五张表 count 均为 `0`，证明 child-first aggregate deletion。
- `pg_constraint` 检查得到两张 parent 表的两个 exactly-one CHECK 和四个 `ON DELETE RESTRICT` FK 共 `6` 个。一次性 SQLAlchemy/asyncpg SAVEPOINT probe 成功插入每张表各一条 User owner + UserGroup owner；两张表的 both/neither 四种写入均被各自 CHECK 拒绝，删除 User/UserGroup owner 均被对应 Environment owner FK 的 RESTRICT 拒绝。初次 probe 把多条 SQL 交给单个 asyncpg prepared statement，按驱动语义失败且事务无写入；拆成单 statement 后完整通过，不是产品 failure。
- `uv run alembic downgrade e35a1d7c9b20` → version 为 predecessor、两张表仅有 `owner_workspace_id`、五张 asset 表 count 均为 `0`；随后 `uv run alembic upgrade c471ac39f002` → version 为 target、两张表仅有 `owner_user_id,owner_user_group_id`、五张 asset 表仍为 `0`、owner constraints count 为 `6`。
- Cleanup：`docker compose ... down --volumes --remove-orphans` → container、network、`w107i39pg2dcf53f979_db-data` 均 Removed；`docker volume inspect w107i39pg2dcf53f979_db-data` → expected exit 1 `no such volume`；临时 override 删除后 `exists=False`。

## 2026-08-18 targeted independent re-review

- 结论：`PASS`。
- 覆盖：personal adapter Activity scope 修复、unscoped `latest_version` 删除及相应 reverify evidence；无新增 finding。
- 发布边界：候选可提交并创建 PR；Issue 在 PR 合并前保持 active，不归档 journal。
