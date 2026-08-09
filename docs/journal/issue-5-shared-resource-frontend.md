# Issue #5: Shared Resource 前端页面

- 类型：`feat` / `type: feature`
- 模块：`area: frontend`
- 优先级：`priority: P0`
- 关联 Milestone：M3 Reusable Run
- 依赖：Issue #4 (Shared Resource 核心实现)

## 背景

Issue #4 已完成 Shared Resource 后端的领域对象、数据库、API 和 Input Binding 集成。
当前前端仅有 API 类型定义（`schema.d.ts`）和 Activity/Notification 的 action 文案，
没有 Shared Resource 的独立页面。`targetPath()` 和 `notificationPath()` 对
`shared_resource` / `shared_resource_version` 均返回 `null`（详见
`journal/2026-08-06-issue-3-shared-resource-core.md` §前端留空）。

设计文档 §2.6 列出了 Shared Resource 的 Core 级别前端能力，本次实现其中与
Workspace SR 查看/创建/版本管理相关的部分。Platform 公共资源页面同样预留，
但不需单独数据注入入口。

## 目标

- 用户可在 Workspace 页面中浏览该 Workspace 持有的 Shared Resource
- 用户可查看 Shared Resource 详情（基本信息 + 版本列表）
- 用户可创建 Shared Resource、修改名称和说明
- 用户可上传文件形成首个版本，以及发布新版本
- 用户可查看版本中的文件列表和文件内容
- 现有 Activity/Notification 的 `targetPath`/`notificationPath` 从 `null` 改为
  实际页面链接

## 范围

### 路由

- `/workspaces/:workspaceId/shared-resources` — Workspace SR 列表（嵌在
  WorkspacePage 内作为 tab）
- `/shared-resources/:resourceId` — 资源详情页（含版本列表）
- `/shared-resource-versions/:versionId` — 版本详情页（含文件列表）

### 页面与组件

- **SharedResourceList**：表格/卡片列出当前 Workspace 的 SR，支持创建按钮、
  点击进入详情。同时列出该 Workspace 可见的 Platform 资源（如有）。
- **SharedResourceDetailPage**：显示资源名称、说明、所有者、版本列表（按序
  号倒序），顶部有编辑按钮和"发布新版本"按钮。
- **CreateResourceModal**：名称 + 说明表单，提交后跳转到详情页。
- **EditResourceModal**：修改名称和说明。
- **PublishVersionModal**：文件上传（拖拽/选择 + prefix 前缀）+ 版本说明，
  multipart 提交。
- **SharedResourceVersionDetailPage**：版本信息（v1/v2...、创建时间、创建者、
  说明）+ 文件列表（路径、大小），点击单个文件可预览文本内容。

### Activity / Notification 联动

- `actions.ts:targetPath()`：`shared_resource` → `/shared-resources/{id}`，
  `shared_resource_version` → `/shared-resource-versions/{id}`
- `notificationTypes.ts:notificationPath()`：同上

### Platform 资源展示

- Workspace SR 列表中可切换 tab 查看 Platform 公共资源（读路径已在后端
  `GET /catalog/shared-resources` 预留）
- Platform 资源详情页：只读展示，不显示编辑/上传按钮

## 验收条件

- 可在 Workspace 页面中创建 Shared Resource，填写名称后跳转到详情页
- 可在详情页上传文件形成版本，上传后版本列表中出现新版本
- 可在版本详情页查看文件列表，点击文件预览文本内容
- 修改资源名称/说明后列表和详情页即时反映
- `targetPath` 和 `notificationPath` 对 `shared_resource` /
  `shared_resource_version` 返回实际路径，而非 `null`
- Activity 流中 Shared Resource 相关条目可点击跳转

## 非目标

- Shared Resource 搜索和筛选（§2.6 A V1）
- 资源目录/样例预览（§2.6 A V1）
- 在 Run Configuration 中通过 UI 选择 SR 版本作为 InputBinding（§2.6 B Core，
  后端已完成，前端留给后续 Issue）
- 资源授权管理（§2.6 D）
- 跨 Workspace Asset Grant（M4）
- 从 Artifact / Project 文件发布为 Shared Resource（V1）
- 删除 Shared Resource（design.md 规定 Platform/Workspace 可以删除 SR，
  但 §2.6 Core 能力列表未包含，后续 Issue 补后端 + 前端）
- 弃用/归档资源版本（§2.6 C V1）