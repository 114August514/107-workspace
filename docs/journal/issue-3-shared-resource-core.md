# Issue #3: Shared Resource 核心实现

- 类型：`feat` / `type: feature`
- 模块：`area: resource`
- 优先级：`priority: P0`
- 关联 Milestone：M3 Reusable Run

## 背景

设计文档 §2.6 和 §3.1.3 规定了 Shared Resource（共享资源）——独立于 Project 存在、
可版本化、可被多个 Project 通过 Input Binding 引用的内容资源。典型用途：数据集、
预训练权重、语料库、预处理脚本等。

当前 `InputBinding` 和 `InputSourceType` 已预留了 `shared_resource_version` 枚举值
和 `SharedResourceVersion → InputBinding → Run` 的引用链路，但 Shared Resource 本身
的领域对象、数据库表、服务层和 API 均不存在。因此 Input Binding 实际上只能走
Artifact 一条路——而 Artifact 是 Run 的输出，不是一手数据集。

本次仅实现设计稿中标记为 `[Core]` 的能力子集。

## 目标

- 用户可以在 Workspace 中创建 Shared Resource、上传文件形成版本
- 用户可在 Run Configuration 的 Input Binding 中引用 SharedResourceVersion
- Run 执行时平台将引用的 Shared Resource 文件挂载到 inputs 目录（只读）
- 用户可浏览本 Workspace 持有的 Shared Resource（Platform 公共资源读路径已预留，数据由 V2 公共发布流程注入）

## 范围

### 领域层

- `SharedResource`（可变，Workspace 或 Platform 持有）
- `SharedResourceVersion`（不可变，GR-201）
- `SharedResourceFile`（不可变，path + size + content_hash）

### 数据库

- `shared_resources` 表
- `shared_resource_versions` 表（含 files JSON 列，和当前 `run_snapshots` 同模式）
- `shared_resource_version_files` 表（path / size / content_hash）
- Alembic 迁移

### 仓储层

- `SharedResourceRepository` 协议（domain/ports/repositories.py）
- 实现（infrastructure/db/repositories.py）
- 查询需要区分 Platform 资源（`owner_workspace_id IS NULL`）和 Workspace 资源（按 membership 过滤）

### 服务层

- `SharedResourceService`：创建、查看、版本管理、文件上传

### API

- `GET /catalog/shared-resources` — Platform 资源，全平台可见
- `GET /workspaces/{id}/shared-resources` — Workspace 资源，成员可见
- `GET /shared-resources/{id}` — 资源详情（含版本列表）
- `POST /workspaces/{id}/shared-resources` — 创建资源
- `POST /shared-resources/{id}/versions` — 上传文件形成新版本
- `GET /shared-resource-versions/{id}` — 版本详情

### Input Binding 集成

- `run_service.py:_check_inputs` 增加 SharedResourceVersion 分支（存在性、可见性）
- `run_service.py:_revalidate_snapshot` 同上
- `run_lifecycle.py:_join_working_directory` / `prepare_run_directory` 处理 SharedResourceVersion 的 materialize（复用已有 blob store，不用新代码路径）

### 测试

- 领域对象单元测试（不可变性、校验）
- 仓储集成测试（按归属过滤）
- 服务单元测试（创建、上传、跨 Workspace 隔离）
- API 集成测试（权限、CRUD）
- smoke test 加入 Shared Resource 闭环

### 顺手整理

按 AGENTS.md 的"路过时顺手收拾"原则，本次会顺手拆分以下文件：

- `domain/models.py` — 拆出 `identity.py`、`project.py`、`run.py`、`activity.py`
- `domain/ports/repositories.py` — 拆出各仓储端口文件
- `infrastructure/db/repositories.py` — 拆出各仓储实现文件

## 验收条件

- [ ] `make check` 全绿
- [ ] 创建 Workspace Shared Resource → 上传文件 → 发布版本 → 在 Input Binding 中引用 → 提交 Run → Run 成功执行并读取到输入数据
- [ ] 本 Workspace 成员能看到本 Workspace 的 Shared Resource，其他 Workspace 成员不能
- [ ] SharedResourceVersion 创建后内容不可修改
- [ ] 已有 Run Snapshot 不因 SharedResourceVersion 变化而受影响

> Platform 公共资源（§2.6 D V2）通过公共发布申请 → 平台管理员审核流程产生，
> 不在本 Core 子集范围。本 Issue 只实现 Workspace 资源写路径；
> Platform 资源的模型/表/字段已在数据层预留给 V2 使用。

## 非目标

- [ ] 跨 Workspace Asset Grant（M4，单独 Issue）
- [ ] 从 Artifact 发布为 Shared Resource（V1，单独 Issue）
- [ ] 从 Project 文件/目录发布为 Shared Resource（V1）
- [ ] 从外部存储导入 Shared Resource（V1）
- [ ] 资源搜索、预览（V1）
- [ ] 弃用/归档资源版本（V1）
- [ ] 使用追踪（V1）
- [ ] 公共发布审核（V2）
- [ ] Template、Profile（Optional Enhancement）