# Issue #3: Shared Resource 核心实现

- 状态：已完成（核心子集）
- 认领：August / Codex
- 上下文：分支 `feat/3-shared-resource-core`，提交 `05e27d0`
- 开始：2026-08-06
- 结束：2026-08-06

## 意图

实现设计稿 §2.6 与 §3.1.3 中的 Shared Resource 核心能力，让 M3 Reusable Run 的
「创建资源 → 上传文件 → 在 Input Binding 中引用 → Run 读取到输入」闭环得以成立。
此前 `InputBinding` 与 `InputSourceType.SHARED_RESOURCE_VERSION` 已预留枚举值，
但 Shared Resource 的领域对象、表、服务和 API 全部缺失，Input Binding 实际只能
走 Artifact 一条路。

## 实际改动

### 领域层

- `domain/models.py`：新增 `SharedResource`（可变，由 Workspace 或 Platform 持有）、
  `SharedResourceVersion`（不可变，GR-201）、`SharedResourceFile` 三个 dataclass。
  `SharedResource.is_platform_owned` 用 `owner_workspace_id is None` 表达 Platform
  持有，避免再开一个布尔字段。`SharedResourceVersion` 暴露 `label`/`total_size`/
  `file_count` 三个派生属性供 presenter 直接用。
- `domain/ids.py`：新增 `SHARED_RESOURCE = "shr"` 与 `SHARED_RESOURCE_VERSION = "shrv"`
  两个前缀。
- `domain/capabilities.py`：新增 `SHARED_RESOURCE_VIEW` / `MANAGE` /
  `VERSION_CREATE` 三项能力。VIEW 进 `_VIEW_ONLY`，MANAGE 与 VERSION_CREATE 进
  `_CONTRIBUTE`，标签写入 `CAPABILITY_LABELS`。
- `domain/enums.py`：`ActivityAction` 增加 `SHARED_RESOURCE_CREATED` /
  `SHARED_RESOURCE_UPDATED` / `SHARED_RESOURCE_VERSION_PUBLISHED`；
  `TargetType` 增加 `SHARED_RESOURCE` / `SHARED_RESOURCE_VERSION`。
- `domain/ports/repositories.py`：新增 `SharedResourceRepository` Protocol，
  覆盖 `add` / `get` / `update` / `list_platform` / `list_for_workspace` /
  `add_version` / `get_version` / `list_versions` / `latest_version` /
  `next_version_sequence`。`Repositories` 容器新增 `shared_resources` 字段。
- `domain/ports/storage.py`：新增 `RunInput` dataclass，把 `prepare_run_directory`
  的 `inputs` 参数从 `list[tuple[str, str]]` 升级为 `list[RunInput]`。`RunInput`
  按 `source_type` 携带 `source_id` / `access_path` / `files`，与设计稿把
  InputBinding 视为对 Content Version 的统一引用一致——artifact 与
  shared_resource_version 只是两种来源，物化方式不同但都暴露在同一 `access_path`
  下、都只读（GR-404）。

### 基础设施层

- `infrastructure/db/tables.py`：新增 `SharedResourceRow`（`owner_workspace_id`
  可空，NULL 表示 Platform 持有）、`SharedResourceVersionRow`（带
  `UniqueConstraint(shared_resource_id, sequence)`）、`SharedResourceVersionFileRow`
  （复合主键 `version_id` + `path`，自然阻止同版本内重复路径）。
- `migrations/versions/fdb5011fe3b2_shared_resources.py`：新建迁移，`down_revision`
  指向 `b48640074b91`。docstring 写明必要性：M3 闭环需要三张表，且 AGENTS.md
  虽规定不擅自改 migration，但**新增**迁移不在「改历史」之列，单独成文件可被
  审阅且不影响既有迁移链。
- `infrastructure/db/repositories.py`：新增 `SharedResourceRepositoryImpl`，
  按 `owner_workspace_id IS NULL` 过滤 Platform 资源，按 `owner_workspace_id = ?`
  过滤 Workspace 资源。新增 `_to_shared_resource` 与 `_hydrate_version` 两个
  转换函数。`SqlRepositories` 实例化 `shared_resources`，并在 `_RULES` 中登记
  `uq_shared_resource_version_seq` 冲突规则（并发发布同序号时映射为 `ConflictError`）。
- `infrastructure/storage/local.py`：`_prepare_sync` 拆出 RunInput 分支——
  `ARTIFACT` 走 `copytree(self._artifacts / source_id, target)`，`SHARED_RESOURCE_VERSION`
  按 `(path, content_hash)` 列表从 blob 池物化到 `access_path` 下。两者在循环外
  统一 `_make_readonly(paths.inputs)` 保证 GR-404。SharedResourceVersion 不另开
  存储目录，复用 ProjectVersion 已在用的 blob 池，去重和不可变性天然成立。

### 应用层

- `application/access.py`：新增 `SharedResourceAccess` dataclass 与
  `AccessGuard.shared_resource` / `shared_resource_version` 两个方法。Platform
  持有的资源对所有登录用户可见但 `role=None`——只读，任何写操作都会因
  `require()` 找不到角色而失败，自然实现「Platform 资源由平台维护，API 不接受
  修改」的口径。
- `application/shared_resource_service.py`：新建服务，覆盖
  `list_platform` / `list_for_workspace` / `get` / `list_versions` / `get_version`
  （查询）与 `create` / `update` / `publish_version` / `read_version_file`（写入）。
  - 名称 / 描述长度按 `MAX_RESOURCE_NAME_LEN=128` / `MAX_RESOURCE_DESCRIPTION_LEN=4096`
    限制；版本描述上限 `MAX_VERSION_DESCRIPTION_LEN=4096`。
  - `_normalize_path` 拒绝绝对路径与 `..`，防止越权写入。
  - `publish_version` 校验同版本内路径唯一、单文件不超过 `max_file_bytes`，
    按 `next_version_sequence` 取序号，逐个 `write_blob` 后一次性 `add_version`。
  - Platform 资源的 `update` / `publish_version` 直接 `raise PermissionDenied`，
    保持「平台维护」语义。
- `application/run_service.py`：`_check_inputs` 与 `_revalidate_snapshot` 各增加
  `SHARED_RESOURCE_VERSION` 分支，调用新提取的 `_check_shared_resource_version_input`
  做存在性 + 可见性校验（Platform 资源全可见，Workspace 资源要求
  `owner_workspace_id` 匹配）。`_submit` 不再直接传 tuple 列表，改为先调用
  `_materialize_inputs` 翻译出 `list[RunInput]` 再交给 storage——Artifact 走
  源 ID，SharedResourceVersion 从仓储取 `(path, content_hash)` 元组塞进 `files`。
  两条路径在 storage 层汇合，run_service 不感知物化细节。

### API 层

- `api/schemas.py`：新增 `SharedResourceOut` / `SharedResourceVersionFileOut` /
  `SharedResourceVersionOut` / `SharedResourceVersionDetailOut` /
  `SharedResourceDetailOut` / `SharedResourceCreateIn` / `SharedResourceUpdateIn` /
  `SharedResourceVersionCreateIn` 共 8 个 Pydantic 模型。
- `api/presenters.py`：新增 `shared_resource_out` / `shared_resource_detail_out` /
  `shared_resource_version_out` / `shared_resource_version_detail_out` 四个
  presenter，统一 domain → schema 的转换。
- `api/routes/catalog.py`：新增 `GET /catalog/shared-resources`，列出 Platform
  持有的资源（不按用户区分）。
- `api/routes/shared_resources.py`：新建路由文件，覆盖
  - `GET    /workspaces/{id}/shared-resources`
  - `POST   /workspaces/{id}/shared-resources`
  - `GET    /shared-resources/{id}`
  - `PATCH  /shared-resources/{id}`
  - `POST   /shared-resources/{id}/versions`（multipart/form-data，`files` + `prefix`）
  - `GET    /shared-resource-versions/{id}`
  - `GET    /shared-resource-versions/{id}/files/content`（按 `path` 查询参数取文件）
- `api/routes/__init__.py`：注册新路由。
- `api/deps.py`：`Services` 容器新增 `shared_resources: SharedResourceService`，
  在 `build_services` 中按 `repos / guard / clock / storage / activity / max_file_bytes`
  装配，保持「路由拿不到仓储、存储和调度器」的边界。
- `contracts/openapi.json` 与 `frontend/src/api/schema.d.ts`：由
  `make contract` 重新生成，包含新端点与新 schema。

## 仓外副作用

无。本次纯后端实现，未对接学校统一身份认证（设计稿 2.1 [V1]），未触碰 Slurm
调度，未修改任何外部系统。

## 验收

- `make check backend` 全绿：lint、format、127 项测试全部通过（含 24 项 Shared
  Resource 新增测试）。
- `make build backend` 通过：`workspace107-0.1.0.tar.gz` 与 wheel 构建成功。
- `make contract check` 通过：OpenAPI 与前端 `schema.d.ts` 与后端一致。
- 已提交到 `feat/3-shared-resource-core` 分支，未触碰 main。

### 测试覆盖

补充测试后实际跑出了两个真实 bug，已修复：

1. **`run_configuration_service._build_fields` 硬编码只接受 artifact**：
   原代码对 `source_type != ARTIFACT` 一律抛 ``ValidationFailed("当前迁移实现
   只支持把 Artifact 作为 Run 输入")``。改为接受 artifact 与
   shared_resource_version 两种已知类型，未知类型显式报错；存在性/可见性校验
   仍在 run_service.preflight 里做。
2. **`publish_version` 路由用 Pydantic 模型接 multipart form**：
   ``payload: SharedResourceVersionCreateIn`` 在 multipart 请求下被 FastAPI
   当 JSON body 解析，导致带 files 的请求一律 422。改成 ``description: str =
   Form(default="")`` 后正常；删除不再使用的 schema。

新增测试分布：

- ``tests/conftest.py`` 与 ``tests/helpers.py``：从 archive 移植，提供
  settings/context/services/client 夹具和 wait_for_run / create_project_with_version
  / use_default_environment 辅助函数。helpers.py 去掉过时的 GR-015 引用以免
  触发架构测试 ``test_active_code_gr_references_exist_in_current_design``。
- ``tests/integration/resource/test_shared_resource_service.py``：19 项服务层
  测试，覆盖 create / update / publish_version / read_version_file 的边界校验、
  权限拒绝、路径规范化、Platform 资源保护、跨 Workspace 隔离、活动记录、blob 去重。
- ``tests/integration/resource/test_shared_resource_input_binding.py``：5 项闭环
  测试，走完 创建资源 → 上传版本 → InputBinding 引用 → 提交 Run → Run 读取
  输入 → 输入只读（GR-404）全流程，覆盖多文件/子目录物化和跨 Workspace 拒绝。
- ``tests/`` 各级补齐 ``__init__.py`` 让 ``from tests.helpers import ...`` 可用。

未完成项（按设计稿非目标，留作后续 Issue）：

- 跨 Workspace Asset Grant（M4）
- 从 Artifact / Project 文件 / 外部存储发布为 Shared Resource（V1）
- 资源搜索、预览、归档、使用追踪（V1）
- 公共发布审核（V2）
- Template、Profile（Optional Enhancement）

## 对 AGENTS.md 规则的两处例外

用户明确批准两处例外，已在记忆 `feedback_agents_exceptions.md` 中记录：

1. **新增 Capabilities 枚举值**：AGENTS.md 规定不擅自扩 Capabilities，但用户
   认为「不能因适应规则而牺牲功能」——Shared Resource 没有 VIEW/MANAGE/
   VERSION_CREATE 三项能力就无法做权限控制。本次新增三个值并加入对应角色集合。
2. **新增 Alembic 迁移文件**：AGENTS.md 规定不擅自改 migration，但本次是**新增**
   迁移而非修改既有迁移，且 Shared Resource 三张表是 M3 闭环的必要前提。新迁移
   `fdb5011fe3b2_shared_resources.py` 单独成文件，docstring 写明必要性，不影响
   既有迁移链。

## 回退方式

回退本任务提交即可。`fdb5011fe3b2_shared_resources.py` 是新增迁移，`down_revision`
指向既有链尾 `b48640074b91`，回退后既有迁移链不受影响。如需回滚数据库，
`alembic downgrade b48640074b91` 即可。

## 禁区遵守

- 未修改任何既有 migration 文件。
- 未修改认证相关代码（`api/deps.py:get_current_user` 的 `X-User` 头逻辑保持不变）。
- 未修改 `domain/models.py` 中的 `InputBinding` 定义（仅消费其 `source_type` 字段）。
- 未牺牲 Capabilities 功能性：新增的三项能力完整接入角色集合与标签。
- 严格遵循分层：API → application → domain ← infrastructure，路由不接触仓储、
  存储和调度器，权限校验和事务边界在服务层。

## 关键设计决策

### 为什么 SharedResourceVersion 不单独开存储目录

Artifact 有 `<storage_root>/artifacts/<artifact_id>/` 目录，因为 Artifact 是 Run
的输出，收集时一次性把工作目录里的产物拷贝过去。SharedResourceVersion 不一样：
它的文件来自用户上传，上传时就已经写进 blob 池（按内容寻址去重），版本只是
`(path, content_hash)` 的列表。如果在 storage 里再开一个目录把内容拷贝一份，
既浪费空间又破坏内容寻址的去重。所以 storage 层直接按 version.files 里的
`(path, content_hash)` 列表从 blob 物化到 Run 的 inputs 目录下，与 ProjectVersion
复用同一个 blob 池。

### 为什么 RunInput 用 dataclass 而不是 tuple

设计稿 §3.1.3 把 InputBinding 定义为对 Content Version 的统一引用，artifact 和
shared_resource_version 只是两种来源。如果 storage 端继续用 `tuple[str, str]`
表达 artifact 输入，再开一个 `tuple[str, list[tuple[str, str]]]` 表达
shared_resource_version，签名就要变成 `inputs_artifact: ..., inputs_version: ...`
或者 `inputs: list[tuple[str, str] | tuple[str, str, list[tuple[str, str]]]]`，
两种都不如一个带 `source_type` 的 dataclass 清晰。`RunInput` 让 storage 端有
一个统一入口，run_service 按 `source_type` 决定如何填充 `files`，未来加新来源
类型只要扩 `RunInput` 的字段即可。

### 为什么 Platform 资源用 `role=None` 而不是新建一个角色

Platform 资源对所有登录用户可见，但只能由平台维护。如果新建一个 `PlatformReader`
角色，每个能读的用户都要被赋予这个角色，而它的能力其实就是「读」——和
`_VIEW_ONLY` 里的能力完全重合。用 `role=None` 表达「只读，无任何写权限」更直接：
`AccessGuard.require()` 在 `role=None` 时任何 `require(cap)` 都会失败，自然禁止
所有写操作，无需新增角色和对应的授权逻辑。

## 后续工作

- 补充针对 Shared Resource 的单元测试与集成测试，覆盖创建、上传、跨 Workspace
  隔离、版本不可变性、Input Binding 闭环等场景。
- 在 smoke test 中加入 Shared Resource 闭环。
- 考虑按设计稿「顺手整理」原则拆分 `domain/models.py` 与
  `infrastructure/db/repositories.py`（本次未做，避免 PR 范围过大）。
