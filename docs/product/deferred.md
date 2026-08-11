# 延后事项与工程妥协登记

本文件是未来产品 / 领域设计延后项和已接受工程 / 代码妥协的唯一活动登记。登记项不构成当前产品规范，也不得覆盖 `docs/product/design.md`、生成式 API Contract 或 Active GR 的目标语义；它只说明当前偏差、支持环境、约束和退出条件。

## 登记规则

每项必须使用稳定 ID，且逐项填写：类别与状态、日期、影响范围 / 文件、预期行为与当前偏差、原因与可见价值、用户 / 安全 / 数据影响、Containment 与支持环境、责任人及 Issue / PR / commit、目标状态与退出条件、复评触发器、解决证据。状态使用 `Deferred`、`Accepted-for-Competition`、`Scheduled`、`In Progress`、`Resolved`、`Superseded` 或 `Won't Fix`；受限接受项必须在 Containment 中明确范围外为 Blocked。

工程 / 代码妥协必须在引入它的 PR 之前或同一 PR 中登记，不能用模糊的一揽子条目代替具体偏差。唯一例外是 2026-08-11 建立本登记前已经存在、且无法唯一恢复引入提交的旧妥协：必须明确标记为“legacy-baseline exception”，记录活动迁移基线 commit / PR 和当前接受 ADR；该例外不得用于之后的新妥协。登记不授权违反当前设计、契约或不可延后的环境边界。普通缺陷保留为 Issue，在途状态进入 Journal，高影响且长期有效的决定进入 ADR；本文件不替代这些载体。

事项进入正式设计或实现时，应把规范迁移到对应设计文档，把工作纳入 Issue，并保留本条目的状态和链接；只有目标达成且记录验证证据后才能标记 `Resolved`。ID 不删除、不复用，后续变化通过 `Superseded` 链接新条目。

---

## Domain / Product

### TODO-DOM-001 — Gallery 与可共享资产模型

- 类别 / 状态 / 日期：Product / `Deferred` / 既有登记，治理元数据补于 2026-08-11
- 影响范围：Gallery、Template、Profile、Environment、Shared Resource 的发布与发现语义
- 预期 / 当前偏差：长期可能形成统一可共享资产模型；当前不建立该抽象
- 原因与价值：避免在真实 Gallery / Explore 需求出现前固定过早抽象
- 影响与 Containment：当前 Roadmap 不承诺 Gallery；无当前安全或数据放宽
- 责任人与关联：Product 维护者；正式设计前创建并关联 Issue / PR
- 目标 / 退出条件 / 复评：完成正式 Gallery / Explore 设计并迁移规范；触发器为该方向进入 Roadmap
- 解决证据：待补

当前暂不设计 Gallery / Explore 以及统一的 `Shareable Asset` 抽象。

未来需要重新评估：

- Template、Profile、Environment、Shared Resource 的统一发布与发现模型；
- Visibility；
- Gallery Listing；
- Asset Transfer；
- Community / Featured 等展示语义；
- 是否需要统一的 Shareable Asset 抽象。

重新评估时机：正式设计 Gallery / Explore 时。

---

### TODO-DOM-002 — Official Asset 与官方资产库

- 类别 / 状态 / 日期：Product / `Deferred` / 既有登记，治理元数据补于 2026-08-11
- 影响范围：Official Asset、Official Library、Community / Featured 及 Ownership
- 预期 / 当前偏差：长期可能建立官方资产治理；当前不新增 Official Asset 核心模型
- 原因与价值：先复用已有 Workspace Ownership，避免未验证的新所有权类型
- 影响与 Containment：当前产品不承诺官方资产库；无当前安全或数据放宽
- 责任人与关联：Product 维护者；正式设计前创建并关联 Issue / PR
- 目标 / 退出条件 / 复评：完成官方资产治理设计并迁移规范；触发器为官方库进入 Roadmap
- 解决证据：待补

当前暂不将 Official Asset 纳入核心领域模型。

未来需要考虑：

- Community、Featured、Official 的语义；
- 平台如何从高质量社区资产形成 Official Asset；
- Official Template / Profile Library；
- Promote 是否创建官方副本；
- Creator Attribution 与 Source Provenance；
- 官方资产由普通 Collaborative Workspace 持有，还是引入其他 Ownership 模型。

当前倾向：官方库优先建模为平台运营方维护的 Collaborative Workspace，而不是新增 Workspace 类型。

---

### TODO-DOM-003 — Course Profile

- 类别 / 状态 / 日期：Product / `Deferred` / 既有登记，治理元数据补于 2026-08-11
- 影响范围：Course Profile、Assignment、Submission 与课程角色工作流
- 预期 / 当前偏差：长期用 Course Profile 验证扩展机制；当前不建立课程专用领域对象
- 原因与价值：先稳定 Workspace、Project、Run、版本与权限基础语义
- 影响与 Containment：当前产品不承诺课程流程；任何原型仍不得绕过既有 GR
- 责任人与关联：Product 维护者；正式设计前创建并关联 Issue / PR
- 目标 / 退出条件 / 复评：完成课程场景领域设计并迁移规范；触发器为课程能力进入 Roadmap
- 解决证据：待补

当前不设计 Course 专用领域对象。

未来以 Course Profile 验证 Profile 扩展机制，并根据实际需要考虑：

- Assignment；
- Submission；
- Instructor / TA / Student；
- Trusted Evaluation；
- 课程场景工作流。

Course Profile 不得绕过 Workspace、Project、Run、权限与版本规则。


---

## Engineering / Code Compromises

### DEFER-CODE-001 — 受控演示身份替代 USTC CAS

- 类别 / 状态 / 日期：Authentication / `Accepted-for-Competition` / 2026-08-11
- 影响范围 / 文件：`backend/src/workspace107/api/deps.py`、`backend/src/workspace107/config.py`、`frontend/src/api/client.ts`、`frontend/src/components/layout/UserSwitcher.tsx`
- 预期 / 当前偏差：长期通过 Identity Provider 接入 USTC CAS；当前实现使用 `X-User` 开发身份并自动建立用户
- 原因与可见价值：延后 CAS 协议和登录 UX，把比赛时间用于可见端到端能力
- 用户 / 安全 / 数据影响：调用方可选择的 Header 不能证明真实身份，不得用于共享或不受信任环境
- Containment / 支持环境：仅本机或受信任操作者演示；现有服务端 Ownership、Membership、Role 和对象范围校验必须保留；共享环境在接入不可伪造身份前为 Blocked
- 责任人与来源：Workspace107 维护者；legacy-baseline exception，活动迁移基线 `a5958a7` / PR #2；当前接受 ADR-0003
- 目标 / 退出条件：接入并验证 CAS，或为目标共享环境提供经验证的可信身份 Adapter；伪造身份失败且映射稳定
- 复评触发器：首次共享演示、USTC 集成部署或身份相关代码变更
- 解决证据：待补

### DEFER-CODE-002 — 比赛沿用固定角色能力策略，不建设可配置权限治理

- 类别 / 状态 / 日期：Authorization Policy / `Accepted-for-Competition` / 2026-08-11
- 影响范围 / 文件：`backend/src/workspace107/domain/enums.py`、`backend/src/workspace107/domain/capabilities.py`、`backend/src/workspace107/application/access.py`、`backend/src/workspace107/application/workspace_service.py`、`frontend/src/components/workspace/MemberPanel.tsx`、`frontend/src/utils/roles.ts`
- 预期 / 当前偏差：长期可按真实需求增加自定义角色、成员组 / 批量授权、Project 级权限、策略例外和完整审计查询；比赛沿用当前固定 Owner / Admin / Member / Viewer 到 Capability 的映射、Owner 转移规则和现有成员管理界面
- 原因与可见价值：复用已经可操作的邀请、角色调整、Owner 转移和服务端 Capability 校验，把比赛时间用于端到端功能切片
- 用户 / 安全 / 数据影响：当前策略不可由运营方配置，也不代表完整生产授权与审计治理；所有已暴露操作仍必须经过现有服务端 Ownership、Membership、Capability 和对象范围校验，不能由前端入口可见性替代
- Containment / 支持环境：只支持文中列出的固定角色能力策略；需要自定义角色、成员组、Project 级授权、策略例外或完整审计检索的场景为 Unsupported，不得用手工数据修改伪装为已支持
- 责任人与来源：Workspace107 维护者；legacy-baseline exception，活动迁移基线 `a5958a7` / PR #2；当前接受 ADR-0003
- 目标 / 退出条件：先以真实 Host / 部署需求确定新增权限控制，再为其提供明确领域规则、服务端校验、API / UI 和审计证据；现有对象范围校验继续通过
- 复评触发器：原 107 Host 要求当前矩阵外的角色 / 授权、引入 Project 级权限、策略例外或审计查询，或修改 Capability 映射 / AccessGuard
- 解决证据：待补

### DEFER-CODE-003 — API 进程轮询 Run 状态而非独立 Worker

- 类别 / 状态 / 日期：Architecture / `Accepted-for-Competition` / 2026-08-11
- 影响范围 / 文件：`backend/src/workspace107/main.py`、`backend/src/workspace107/application/run_lifecycle.py`
- 预期 / 当前偏差：目标架构由独立 Background Worker 消费异步工作；当前 API lifespan 内的同步循环轮询并回写 Run 状态
- 原因与可见价值：复用当前可运行闭环，优先展示提交、状态、日志与 Artifact
- 用户 / 安全 / 数据影响：不支持多 API 副本的可靠任务归属，不宣称 Worker 边界已经验证
- Containment / 支持环境：单 API 进程的开发或受控演示；多副本、故障恢复或生产部署为 Blocked
- 责任人与来源：Workspace107 维护者；legacy-baseline exception，seam 可追溯至 `374aa9f`，活动迁移基线接受于 `a5958a7` / PR #2；当前接受 ADR-0003
- 目标 / 退出条件：独立 Worker 入口、派发 / 消费边界和故障恢复通过端到端验证
- 复评触发器：多副本部署、真实 Walking Skeleton 或同步可靠性问题
- 解决证据：待补

### DEFER-CODE-004 — 数据库明文 Secret Vault 仅保存演示凭据

- 类别 / 状态 / 日期：Secret Storage / `Accepted-for-Competition` / 2026-08-11
- 影响范围 / 文件：`backend/src/workspace107/infrastructure/db/secret_vault.py`、`backend/src/workspace107/infrastructure/db/tables.py`
- 预期 / 当前偏差：生产环境由合适的 Secret Store 安全保存并在执行边界解析；当前 DatabaseSecretVault 把值直接保存在数据库列中
- 原因与可见价值：保留 Secret 引用、提交前检查和执行注入的可见流程，不提前建设生产 Secret 基础设施
- 用户 / 安全 / 数据影响：数据库泄露会暴露值；登记不能授权保存真实、长期或不可撤销凭据
- Containment / 支持环境：仅使用无长期价值且可立即撤销的演示凭据；真实凭据和共享 / 生产环境为 Blocked
- 责任人与来源：Workspace107 维护者；legacy-baseline exception，活动迁移基线 `a5958a7` / PR #2；当前接受 ADR-0003
- 目标 / 退出条件：替换为经目标环境验收的 Secret Provider，并证明值不进入 Snapshot、API、日志和普通数据库备份
- 复评触发器：首次需要真实凭据、共享部署、备份或 Secret 相关实现变更
- 解决证据：待补

### DEFER-CODE-005 — Mock Scheduler 使用宿主机 Shell

- 类别 / 状态 / 日期：Execution / `Accepted-for-Competition` / 2026-08-11
- 影响范围 / 文件：`backend/src/workspace107/infrastructure/scheduler/mock.py`、`backend/src/workspace107/infrastructure/scheduler/script.py`
- 预期 / 当前偏差：不受信任作业不得在 API 主机运行身份的 Shell 中执行；当前 Mock Scheduler 通过宿主机命令解释器真实执行用户命令
- 原因与可见价值：在没有真实集群时展示 Run 提交、状态、日志和 Artifact 闭环
- 用户 / 安全 / 数据影响：Run 提交者可执行 API 运行身份有权执行的命令；Mock 不是沙箱
- Containment / 支持环境：仅受信任操作者和隔离演示主机，主机不得持有供用户作业继承的真实平台凭据；不受信任用户环境为 Blocked
- 责任人与来源：Workspace107 维护者；legacy-baseline exception，活动迁移基线 `a5958a7` / PR #2；当前接受 ADR-0003
- 目标 / 退出条件：Mock 永不面向不受信任提交者，或被替换 / 限制在无法接触 API 主机资源与凭据的经验证隔离执行边界
- 复评触发器：首次非维护者演示、真实集群接入或 Scheduler 实现变更
- 解决证据：待补

### DEFER-CODE-006 — Local Storage 尚未形成共享部署的文件系统隔离证明

- 类别 / 状态 / 日期：Storage / Path Containment / `Accepted-for-Competition` / 2026-08-11
- 影响范围 / 文件：`backend/src/workspace107/infrastructure/storage/local.py`、`backend/src/workspace107/application/project_service.py`、Run 输入与 Artifact 收集路径
- 预期 / 当前偏差：所有读、写、复制、收集和删除都在解析后的授权根目录内，并在真实 Shared FS 身份与权限下验证；当前 Local Storage 只作为本地实现，尚无共享 / 不受信任部署的完整隔离证据
- 原因与可见价值：保留 Project 文件、Run 工作目录、日志和 Artifact 的本地可见闭环
- 用户 / 安全 / 数据影响：不能据此宣称符号链接、路径别名、共享 UID / GID 和并发清理等生产边界已经受控
- Containment / 支持环境：仅本地受信任演示数据；不受信任输入、共享文件系统和生产部署在路径解析、no-follow 策略及端到端证据完成前为 Blocked
- 责任人与来源：Workspace107 维护者；legacy-baseline exception，seam 可追溯至 `374aa9f`，活动迁移基线接受于 `a5958a7` / PR #2；当前接受 ADR-0003
- 目标 / 退出条件：所有文件操作实施解析后根目录约束和明确的符号链接策略，并通过 traversal、同前缀目录、symlink / hardlink、恶意 ID、受限删除及真实 Shared FS 测试
- 复评触发器：首次共享存储接入、非受信任文件输入或 Storage Adapter 变更
- 解决证据：待补

### DEFER-CODE-007 — 新 Workspace 自动获得全部公开 Compute Plan 权益

- 类别 / 状态 / 日期：Resource Entitlement / `Accepted-for-Competition` / 2026-08-11
- 影响范围 / 文件：`backend/src/workspace107/application/workspace_service.py` 的 `_grant_default_entitlements`、Personal / Collaborative Workspace 创建路径
- 预期 / 当前偏差：长期由管理配置或申请审批产生、调整和撤销 Resource Entitlement；当前每个新 Workspace 自动获得全部公开 Compute Plan，且固定并发额度为 2
- 原因与可见价值：无需先建设资源申请和审批流程即可展示 Workspace 创建、算力方案选择和 Run 提交闭环
- 用户 / 安全 / 数据影响：当前权益不代表真实 107 配额、Account、QoS、审批或资源资格，不能据此授权真实集群资源
- Containment / 支持环境：仅使用 Seed / 演示 Compute Plan 的本地或受控比赛环境；连接真实集群、真实计费 / 配额或多租户资源前为 Blocked
- 责任人与来源：Workspace107 维护者；legacy-baseline exception，活动迁移基线 `a5958a7` / PR #2；当前接受 ADR-0003
- 目标 / 退出条件：实现可审计的 Entitlement 管理或申请审批生命周期，映射并验证真实 Compute Plan / Account / QoS，且新 Workspace 不再无条件获得全部方案
- 复评触发器：首次真实 Slurm 资源接入、资源配额 / 计费启用、Compute Plan 目录变更或 Entitlement 创建逻辑变更
- 解决证据：待补

### DEFER-CODE-008 — 可见 Project Version 使用数据库元数据与内容摘要而非真实 Git

- 类别 / 状态 / 日期：Version Control / `Accepted-for-Competition` / 2026-08-11
- 影响范围 / 文件：`backend/src/workspace107/application/project_service.py`、`backend/src/workspace107/infrastructure/db/repositories.py`、`backend/src/workspace107/infrastructure/storage/local.py` 的 Project File / Version 保存、差异、恢复和 Run materialization 路径
- 预期 / 当前偏差：目标 Project 内容与版本由真实 Git / Version Control Adapter 提供；当前可见版本切片把不可变文件清单和内容摘要写入数据库，并从 Local Storage Blob 恢复 / materialize
- 原因与可见价值：当前替代已经支撑文件编辑、保存版本、查看差异、恢复版本和从确定版本发起 Run 的比赛闭环
- 用户 / 安全 / 数据影响：不提供 Git 仓库互操作、原生 commit / branch / merge 语义或 Git 级可追溯性；不得把序号版本描述为真实 Git 验证
- Containment / 支持环境：仅 Workspace107 内部版本 UI / API 和受控演示数据；需要 Git 协议、外部仓库同步、分支协作或真实 M1 Version Control 证据的场景为 Unsupported
- 责任人与来源：Workspace107 维护者；legacy-baseline exception，活动迁移基线 `a5958a7` / PR #2；当前接受 ADR-0003
- 目标 / 退出条件：实现并装配 Version Control Port / Git Adapter，迁移或明确处理现有版本数据，并通过保存、读取、差异、恢复、Run materialization 和外部 Git 互操作验收
- 复评触发器：真实 M1 Walking Skeleton、Git 协议 / 外部仓库需求、版本数据兼容承诺或 Project Version 持久化变更
- 解决证据：待补

### DEFER-CODE-009 — Mock Run 直接执行用户命令，不做 Apptainer Runtime 准备

- 类别 / 状态 / 日期：Runtime Preparation / `Accepted-for-Competition` / 2026-08-11
- 影响范围 / 文件：`backend/src/workspace107/application/run_service.py`、`backend/src/workspace107/infrastructure/scheduler/script.py`、`backend/src/workspace107/infrastructure/scheduler/mock.py` 的 Environment Version 与提交路径
- 预期 / 当前偏差：目标链路根据固定 Environment Version 准备并进入 Apptainer / Conda / Native Runtime；当前 Snapshot 虽记录 `environment_image` 和 `setup_command`，Mock 会把两者相关信息写入可见脚本，但实际提交只在宿主环境执行用户 `command`，不消费镜像或准备命令
- 原因与可见价值：在 Runtime Adapter 未实现时仍可展示 Environment 选择、不可变 Run Snapshot、提交、日志与 Artifact 闭环
- 用户 / 安全 / 数据影响：Seed 中镜像值不证明镜像已拉取、校验或执行，宿主依赖可能影响结果；本条只登记 Runtime 缺失，宿主机 Shell 的信任隔离仍由 DEFER-CODE-005 单独约束
- Containment / 支持环境：仅依赖已知宿主环境的 Mock 受控演示；需要镜像隔离、环境可复现性、真实 Apptainer 或真实 M1 Runtime 证据的场景为 Unsupported
- 责任人与来源：Workspace107 维护者；legacy-baseline exception，活动迁移基线 `a5958a7` / PR #2；当前接受 ADR-0003
- 目标 / 退出条件：实现 Runtime Port / Adapter，按固定 Environment Version 准备并校验运行环境，并通过镜像获取、身份 / 挂载、失败恢复和真实作业端到端验收
- 复评触发器：真实 M1 Walking Skeleton、Apptainer / Conda 集成、Environment Version 语义变更或首次要求可复现运行证明
- 解决证据：待补
