# 测试与目标对照表

本表把当前长期测试资产映射到它们保护的产品或工程目标。

目标写法约定：

- 已落在 [`../product/design.md`](../product/design.md) 的行为，直接引用其
  `GR-xxx` 规则编号（§3.3）或 `§x.x` 章节号，不复述规则原文；
- 未落 design.md 的，用一句话说明保护目的，并在来源列标注「待进入 design.md」。

来源列含义：`GR-xxx` = design.md §3.3 全局规则；`§x.x` = design.md 对应章节；
「待进入 design.md」 = 该目标当前只在实现与测试中体现，尚无 design.md 权威来源。

## 后端

### unit/

| 测试文件 | 保护目标 | 来源 |
|---|---|---|
| `unit/test_cli.py` | CLI 源文件扫描尊重 .107ignore 与默认排除 | §2.3 / §3.4.3 |
| `unit/application/test_run_version_fields.py` | Run 历史输出携带版本 ID 与标签 | §2.8 / GR-302 |
| `unit/application/test_configuration_access.py` | User Group 配置访问按角色状态控制 | §2.2 / §3.1.4 / GR-103 |
| `unit/application/test_project_paths.py` | 项目文件路径规范化并阻止越出根目录 | §2.3 / §3.4.3 |
| `unit/application/test_scoped_config_resolver.py` | Variable/Secret 按作用域与发起用户解析 | §3.1.4 / GR-105 / GR-304 / GR-307 |
| `unit/application/test_shared_resource_paths.py` | 共享资源路径规范化并阻止越出根目录 | §2.6 / §3.4.4 |
| `unit/domain/test_compute.py` | 算力请求校验、计划限制与调度配置解析 | §2.7 / §3.1.5 / GR-406 |
| `unit/domain/test_config_scope.py` | Secret 引用作用域限定与格式校验 | §3.1.4 / GR-304 |
| `unit/domain/test_shared_resource.py` | 共享资源可变元数据与不可变版本边界 | §2.6 / GR-201 |
| `unit/domain/test_input_binding_subpath.py` | 输入绑定子路径规范化并阻止越出根目录 | §3.1.3 / GR-403 / GR-404 |
| `unit/domain/test_ownership.py` | User 与 User Group 生成不同 Owner 引用 | §3.1.1 / GR-101 |
| `unit/domain/test_secrets.py` | 环境变量表达式解析与 Secret 脱敏 | §3.1.4 / GR-304 |
| `unit/domain/test_slurm_projection.py` | Slurm 事实投影为算力计划可用性 | §2.7 / §3.1.5 / GR-406 |
| `unit/domain/test_run_snapshot.py` | Run Snapshot 序列化与路径约束 | §3.1.6 / GR-202 / GR-302 / GR-303 |
| `unit/infrastructure/test_environment_import.py` | 公共镜像导入的网络边界与内容确定性 | §2.5 / §3.1.3 / GR-205 / GR-206 |
| `unit/infrastructure/test_trusted_proxy_identity.py` | 可信代理头部解析为平台身份 | §2.1 / §3.1.1 / §4.2 |
| `unit/observability/test_context_and_formatters.py` | 请求标识传递与日志格式输出 | 待进入 design.md |

### integration/

| 测试文件 | 保护目标 | 来源 |
|---|---|---|
| `integration/test_api_convergence.py` | 首页活动通知按当前用户与成员边界汇总 | §2.1 / §2.10 / GR-602 / GR-603 |
| `integration/test_notifications_core.py` | 通知读写、偏好隔离与核心事件投递 | §2.10 / GR-604 |
| `integration/test_cli_sync.py` | CLI 增量同步正确应用且隔离未完成传输 | §2.3 |
| `integration/test_run_initiated_by_user.py` | 按发起用户校验并固化配置、支持安全重跑 | GR-105 / GR-202 / GR-205 / GR-301 / GR-302 / GR-303 / GR-304 / GR-306 / GR-307 / GR-401 / GR-403 / GR-405 / GR-406 |
| `integration/test_project_languages.py` | 仅按可见项目最新版本统计语言 | §2.3 / GR-107 / GR-201 |
| `integration/test_environment_publication.py` | 校验并持久化不可变环境版本及导入产物 | §2.5 / GR-201 |
| `integration/test_lifecycle_deletion.py` | 删除前置影响检查与从属生命周期清理 | §2.2 / §2.3 / §2.4 / GR-206 / GR-502 / GR-602 |
| `integration/test_project_sync.py` | 暂存同步经权限复核后应用到工作状态 | §2.3 |
| `integration/test_project_working_state.py` | 项目文件操作、压缩包与路径安全 | §2.3 / 待进入 design.md |
| `integration/test_scoped_config_http.py` | User、Group、Project 配置 CRUD 与 Secret 脱敏 | §2.1 / §2.3 / GR-105 / GR-407 |
| `integration/test_scoped_config_run_execution.py` | 快照取值、重跑资格与失败通知语义 | §2.8 / §2.10 / GR-202 / GR-303 / GR-304 / GR-306 / GR-406 |
| `integration/test_simple_run.py` | 预览确认、配置固定及输出结果一致性 | §2.8 / §2.9 / GR-202 / GR-303 / GR-304 / GR-305 / GR-406 |
| `integration/test_user_entitlements.py` | 权益归发起用户并限制 Run 资源资格 | §2.1 / §2.7 / GR-105 / GR-307 / GR-406 |
| `integration/test_scoped_config_run.py` | 冻结变量值并按精确 Secret 引用解析 | §2.1 / §2.3 / GR-202 / GR-304 / GR-407 |
| `integration/test_scoped_config_fork.py` | Fork 只复制配置表达式不继承作用域值 | §2.4 / GR-407 / GR-501 |
| `integration/test_slurm_projection.py` | 按调度器投影并校验权益后冻结请求 | §2.7 / §2.8 / GR-302 / GR-303 / GR-406 |
| `integration/test_run_reproduce_download.py` | 重跑生成新快照且日志产物下载安全完整 | §2.8 / §2.9 / GR-202 / GR-203 / GR-303 / GR-304 / GR-306 |
| `integration/test_project_ownership.py` | Project Owner、可见性读取与 Fork 边界 | §2.3 / §2.4 / GR-101 / GR-107 / GR-501 / GR-503 |
| `integration/db/test_asset_ownership.py` | 资产必须唯一归属且 Owner 引用不可删除 | GR-101 / GR-401 |
| `integration/db/test_project_ownership.py` | Project 必须唯一归属且 Owner 引用受保护 | GR-101 / GR-306 |
| `integration/db/test_scoped_config_persistence.py` | 同名配置按作用域隔离并安全解析 Secret | §2.1 / §2.3 / GR-105 / GR-304 / GR-407 |
| `integration/db/test_asset_owner_discovery.py` | 发现资产仅限本人或有效组 Owner 范围 | §2.5 / §2.6 / GR-401 |
| `integration/scheduler/test_slurm_batch_io.py` | Slurm 批作业通过平台路径读写输入输出 | §2.8 / §2.9 |
| `integration/identity/test_external_identity.py` | CAS 身份映射稳定且不同认证身份不合并 | §2.1 |
| `integration/identity/test_user_groups.py` | Group 成员角色治理与唯一 Owner 并发安全 | §2.2 / GR-102 / GR-103 / GR-104 |
| `integration/identity/test_user_profile.py` | 当前用户资料修改与认证身份连续性 | §2.1 |
| `integration/storage/test_local_storage.py` | 本地暂存目录隔离、只读与完整性校验 | 待进入 design.md |
| `integration/storage/test_settings.py` | 初始化并幂等准备本地存储与数据库目录 | 待进入 design.md |
| `integration/postgres/test_user_group_postgres.py` | PostgreSQL 并发治理保持有效 Owner | GR-104 |
| `integration/resource/test_asset_owner_use.py` | 按消费 Project Owner 校验资产使用与重跑 | §2.4 / §2.5 / §2.6 / GR-105 / GR-401 / GR-408 / GR-503 |
| `integration/resource/test_cross_owner_use_grant.py` | USE Grant 主体范围及所有权转移失效 | §2.5 / §2.6 / GR-401 / GR-402 / GR-408 |
| `integration/resource/test_platform_shared_resource_input.py` | 平台组资源无特殊绕过且跨 Owner 使用受拒 | §2.6 / GR-401 |
| `integration/resource/test_shared_resource_input_binding.py` | 资源版本精确绑定、只读物化与路径校验 | §2.6 / §3.1.3 / GR-201 / GR-403 / GR-404 |
| `integration/resource/test_shared_resource_subpath.py` | 输入子路径按边界过滤并映射到访问路径 | §3.1.3 / GR-403 |
| `integration/resource/test_shared_resource_publication.py` | 异步发布持久记录且成功只生成一个版本 | §2.6 / GR-201 |
| `integration/resource/test_shared_resource_service.py` | 共享资源管理、版本发布与活动记录 | §2.6 / §2.10 / GR-101 / GR-201 / GR-401 / GR-601 |
| `integration/resource/test_shared_resource_use_qualification.py` | Owner 与 Grant 共同决定资源发现资格 | §2.6 / GR-401 / GR-402 / GR-408 |

### contract/

| 测试文件 | 保护目标 | 来源 |
|---|---|---|
| `contract/test_api_contract.py` | OpenAPI 固化 Group 权限与 Run 发起契约 | §2.2 / §2.8 / GR-103 / GR-104 / GR-105 / GR-307 |
| `contract/test_asset_owner_contract.py` | Owner 摘要及跨 Owner 资产目录契约稳定 | §2.5 / §2.6 / GR-101 / GR-401 / GR-402 |
| `contract/test_scoped_config_contract.py` | 配置路由显式分域且 Secret 不暴露明文 | §2.1 / §2.3 / GR-304 / GR-407 |

### architecture/

| 测试文件 | 保护目标 | 来源 |
|---|---|---|
| `architecture/test_docs_references.py` | 活动代码与文档引用指向当前事实源 | 待进入 design.md |
| `architecture/test_dependency_direction.py` | 后端分层依赖方向符合架构约束 | §4.3 |

## 前端

### component/

| 测试文件 | 保护目标 | 来源 |
|---|---|---|
| `component/AppShell.test.tsx` | 全局导航、Project 上下文与 User Group 分区 | §2.1 / §2.2 |
| `component/AsyncState.test.tsx` | 异步加载态使用调用方明确动作文案 | 待进入 design.md |
| `component/AuthSession.test.tsx` | 登录态确认、401 跳转与会话失效清理 | §2.1 |
| `component/BrandMark.test.tsx` | 品牌标记尺寸与无障碍语义 | 待进入 design.md |
| `component/CreateUserGroupDialog.test.tsx` | 创建 User Group 的表单校验与提交 | §2.2 / §3.4.1 |
| `component/DesignSystemPage.test.tsx` | 设计系统状态、品牌与交互示例 | 待进入 design.md |
| `component/EnvironmentPages.test.tsx` | 环境发现、版本可用性与发布失败重试 | §2.5 / GR-201 / GR-401 |
| `component/FileBrowser.test.tsx` | 项目文件上传、失败反馈与只读入口 | §2.3 |
| `component/FileViewer.test.tsx` | 版本文件只读查看与工作态编辑保存 | §2.3 / §3.4.2 / GR-201 / GR-204 |
| `component/ForkModal.test.tsx` | 按来源与目标 Owner 权限创建 Fork | §2.4 / GR-501 / GR-503 |
| `component/GlobalNavigationDrawer.test.tsx` | 全局工作区导航排序、展开与当前态 | §2.1 |
| `component/HomePage.test.tsx` | 个人首页展示最近 Run、算力与邀请 | §2.1 / §2.2 / §2.7 |
| `component/MemberPanel.test.tsx` | 成员邀请、角色治理、移除与所有权转移 | §2.2 / §3.4.1 / GR-103 / GR-104 |
| `component/NotificationBell.test.tsx` | 通知未读、已读切换、目标导航与偏好 | §2.10 |
| `component/PersonalExecutionContextPage.test.tsx` | 个人 Variable/Secret 与算力权益展示管理 | §2.1 / §2.7 / §3.4.1 |
| `component/ProfilePage.test.tsx` | 个人资料与所属 User Group 展示 | §2.1 / §2.2 |
| `component/ProjectConfigPanels.test.tsx` | Project Variable/Secret 管理及权限边界 | §2.3 / §3.4.2 |
| `component/ProjectLanguages.test.tsx` | 展示最新不可变版本的语言统计 | §2.3 / GR-201 / 待进入 design.md |
| `component/PublishVersionModal.test.tsx` | 共享资源版本发布持久尝试与失败恢复 | §2.6 / GR-201 |
| `component/ReadmePanel.test.tsx` | Project README 的 Markdown 内容预览 | §2.3 |
| `component/RunConfigurationModal.test.tsx` | 运行方案固定环境、输入绑定与资源配置 | §2.3 / §2.5 / §2.6 / §2.7 / GR-205 / GR-403 / GR-406 |
| `component/RunFromVersionModal.test.tsx` | 固定版本与配置预检后提交 Run | §2.8 / GR-302 / GR-303 |
| `component/RunPage.test.tsx` | Run 状态、快照、日志、产物与重跑 | §2.8 / §2.9 / GR-301 / GR-302 / GR-303 / GR-306 |
| `component/RunTable.test.tsx` | Run 表展示版本、发起人及规范链接 | §2.8 / GR-301 / GR-307 |
| `component/SettingsPage.test.tsx` | 账户显示名称、用户名编辑与刷新 | 待进入 design.md |
| `component/SharedResourcePage.test.tsx` | 共享资源版本、Owner 与 USE 资格展示 | §2.6 / GR-401 / GR-402 |
| `component/SharedResourceVersionPage.test.tsx` | 共享资源版本清单与文件预览 | §2.6 / GR-201 |
| `component/UserGroupBoundary.test.tsx` | User Group 分区导航、成员边界与删除确认 | §2.2 / §3.4.1 / GR-103 / GR-104 |
| `component/UserGroupLeave.test.tsx` | Member 可确认退出且 Owner 不可退出 | §2.2 / §3.4.1 / GR-103 / GR-104 |
| `component/UserGroupOverview.test.tsx` | 组概览展示身份、成员与 Project 状态 | §2.2 |
| `component/UserGroupResourceTabs.test.tsx` | 组资源分区按 Owner 过滤并完整分页 | §2.2 / §2.3 / §2.5 / §2.6 |
| `component/UserGroupSettings.test.tsx` | 组名称说明编辑及 Member 设置边界 | §2.2 / §3.4.1 / GR-103 |
| `component/VersionDetailPage.test.tsx` | 版本操作按 capability 控制并支持派生 | §2.3 / §2.4 / GR-503 |
| `component/VersionDiffPanel.test.tsx` | 跨分页选择版本并展示内容差异 | §2.3 / GR-201 |
| `component/VersionPanelChanges.test.tsx` | 未保存变更查看、放弃与只读边界 | §2.3 / §3.4.2 / GR-201 / GR-204 |

### unit/

| 测试文件 | 保护目标 | 来源 |
|---|---|---|
| `unit/activityActions.test.ts` | Activity 链接遵循对象权限与历史边界 | §2.10 / GR-602 / GR-603 |
| `unit/auth-proxy.test.ts` | 登录与后端 API 路由认证分流 | §2.1 / 待进入 design.md |
| `unit/format.test.ts` | Run 时长与时间轴的稳定格式化 | 待进入 design.md |
| `unit/api/client.test.ts` | API 错误信封、401 信号与删除 404 解析 | §3.4.2 / 待进入 design.md |
| `unit/api/sharedResources.test.ts` | 共享资源发布上传与版本文件文本读取 | §2.6 / GR-201 |
| `unit/api/useAsync.test.tsx` | 异步请求 latest-wins 与静默刷新顺序 | 待进入 design.md |

## 说明

- 本表只描述测试**实际保护**的目标，不表示对应 GR 规则已被完整覆盖；
  一条规则可能分散在多个测试中，也可能尚无测试。
- 游离的 `REQ-21-xx` 等局部编号无 design.md 权威来源，本表已将其归一到
  §2.2 等对应能力章节；后续应把这些目标正式落进 design.md。
- 新增或删除长期测试时同步更新本表。
