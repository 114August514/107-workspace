# Issue #5: Shared Resource 前端页面

- 状态：进行中
- 认领：August / Codex
- 上下文：分支 `feat/5-shared-resource-frontend`，基于 `feat/3-shared-resource-core`
- 开始：2026-08-10
- 关联 Issue：#5（依赖 #4 后端实现）

## 意图

后端在 Issue #4 已完成 Shared Resource 的领域对象、API 和 Input Binding 集成。
前端目前只有 `schema.d.ts` 里生成的类型和 `actions.ts` / `notificationTypes.ts`
里的文案，没有 Shared Resource 的独立页面——`targetPath()` 和 `notificationPath()`
对 `shared_resource` / `shared_resource_version` 都返回 `null`。

本 Issue 实现 design.md §2.6 中与 Workspace SR 查看/创建/版本管理相关的 Core
前端能力，让「创建资源 → 上传版本 → 查看版本文件」在前端走通，并把
Activity/Notification 的跳转链接补齐。

## 现状摸底（先搜再写）

前端分层链路：

    后端 DTO → openapi.json → schema.d.ts → types.ts → client.ts → 组件

Shared Resource 相关 schema 与端点已在 `schema.d.ts` 生成：
- `SharedResourceOut` / `SharedResourceDetailOut` / `SharedResourceVersionOut` /
  `SharedResourceVersionDetailOut` / `SharedResourceVersionFileOut` /
  `SharedResourceCreateIn` / `SharedResourceUpdateIn`
- `GET /catalog/shared-resources`（Platform）
- `GET/POST /workspaces/{id}/shared-resources`
- `GET/PATCH /shared-resources/{id}`
- `POST /shared-resources/{id}/versions`（multipart）
- `GET /shared-resource-versions/{id}`
- `GET /shared-resource-versions/{id}/files/content`

现有约定可复用的：
- Modal 模式：`CreateProjectModal.tsx`（Form + antd Modal，submit + message）
- Table 模式：`ProjectTable.tsx`
- 详情页模式：`ProjectPage.tsx`、`RunPage.tsx`（`useParams` + 异步加载）
- API client：`client.ts` 的 `unwrap` + 领域命名函数
- 类型派生：`types.ts` 从 `Schemas[...]` 取别名
- 权限判断：`can(workspace, capability)` —— 不按角色推导，按 capability
- 下载二进制：`downloadArtifactFile` 用 fetch + blob（带 X-User 头）

## 范围

### 1. types.ts 派生类型

```ts
export type SharedResource = Schemas['SharedResourceOut']
export type SharedResourceDetail = Schemas['SharedResourceDetailOut']
export type SharedResourceVersion = Schemas['SharedResourceVersionOut']
export type SharedResourceVersionDetail = Schemas['SharedResourceVersionDetailOut']
export type SharedResourceVersionFile = Schemas['SharedResourceVersionFileOut']
export type SharedResourceCreate = Schemas['SharedResourceCreateIn']
export type SharedResourceUpdate = Schemas['SharedResourceUpdateIn']
```

### 2. client.ts 领域函数

- `listWorkspaceSharedResources(workspaceId)`
- `listPlatformSharedResources()`
- `getSharedResource(id)` → `SharedResourceDetail`
- `createSharedResource(workspaceId, name, description)`
- `updateSharedResource(id, payload)`
- `publishSharedResourceVersion(resourceId, { files, description, prefix })` ——
  multipart，参考后端 `Body_publish_...` 用 `FormData`
- `getSharedResourceVersion(versionId)` → `SharedResourceVersionDetail`
- `readSharedResourceVersionFile(versionId, path)` → 文本内容

### 3. 路由

`App.tsx` 增加：
- `/shared-resources/:resourceId` → `SharedResourcePage`
- `/shared-resource-versions/:versionId` → `SharedResourceVersionPage`

Workspace SR 列表作为 `WorkspacePage` 内的 panel（和 MemberPanel /
EntitlementPanel 同级），不单独开路由。

### 4. 组件

`components/sharedresource/`：
- `SharedResourcePanel.tsx`：嵌在 WorkspacePage，列出本 Workspace SR + Platform SR
  tab 切换，含创建按钮
- `SharedResourceTable.tsx`：表格，点击行跳详情
- `CreateSharedResourceModal.tsx`：照 `CreateProjectModal`
- `EditSharedResourceModal.tsx`：修改名称/说明
- `PublishVersionModal.tsx`：文件上传 + prefix + 说明

`pages/`：
- `SharedResourcePage.tsx`：详情，含版本列表 + 编辑/上传入口
- `SharedResourceVersionPage.tsx`：版本详情，含文件列表 + 文件预览

### 5. Activity / Notification 联动

- `actions.ts:targetPath()`：`shared_resource` → `/shared-resources/{id}`，
  `shared_resource_version` → `/shared-resource-versions/{id}`
- `notificationTypes.ts:notificationPath()`：同上

### 6. Platform 资源只读

Platform SR（`is_platform_owned === true`）在详情页不显示编辑/上传按钮，
列表页和 Workspace SR 同一表格但加标记。

## 非目标

- 在 Run Configuration 里通过 UI 选 SR 版本作 InputBinding（§2.6 B Core，
  后端已完成，前端留给后续 Issue）
- SR 搜索/筛选/预览（V1）
- 资源授权管理（§2.6 D）
- 删除 SR、弃用/归档版本（后续 Issue）
- 跨 Workspace Asset Grant（M4）

## 验收

- 创建资源 → 跳详情 → 上传文件形成版本 → 版本列表出现新版本
- 版本详情页可看文件列表，点击预览文本内容
- 修改资源名称/说明后列表和详情即时反映
- Activity 流中 SR 相关条目可点击跳转
- `make check` 全绿（typecheck + frontend test + build + contract）

## 完成记录（2026-08-10）

实现落地，文件清单：

- `src/api/client.ts`：新增 8 个领域函数
  （listWorkspaceSharedResources / listPlatformSharedResources / getSharedResource /
  createSharedResource / updateSharedResource / publishSharedResourceVersion /
  getSharedResourceVersion / readSharedResourceVersionFile）。multipart 上传手动
  构造 `FormData`，每个文件挂在 `files` 下，`prefix` 走 query，`description` 普通
  字段；契约里 `files: string[]` 与运行时 `File` 对象不一致，按 openapi-fetch
  约定 cast。
- `src/api/types.ts`：派生 7 个 Shared Resource 类型别名。
- `src/components/sharedresource/`：SharedResourceTable / CreateSharedResourceModal /
  EditSharedResourceModal / PublishVersionModal / SharedResourcePanel。Panel 含
  「本空间 / 平台公共」两个 tab，创建按钮按 `shared_resource.manage` 能力收敛。
- `src/pages/SharedResourcePage.tsx`：资源详情 + 版本列表，编辑/发布按钮按
  `shared_resource.manage` / `shared_resource.version.create` 收敛；平台资源
  （`is_platform_owned`）一律只读，不显示入口。
- `src/pages/SharedResourceVersionPage.tsx`：版本详情 + 文件列表 + 文本预览 Drawer。
- `src/App.tsx`：新增 `/shared-resources/:resourceId` 与
  `/shared-resource-versions/:versionId` 两条路由。
- `src/pages/WorkspacePage.tsx`：新增「共享资源」tab，内嵌 SharedResourcePanel。
- `src/components/activity/actions.ts`、`src/components/notification/notificationTypes.ts`：
  `targetPath()` / `notificationPath()` 对 shared_resource / shared_resource_version
  从 `null` 改为实际路径（在上下文切换前已完成）。
- `tests/unit/api/sharedResources.test.ts`：守 multipart 拼装的边界行为
  （files 挂载、prefix 走 query、Content-Type 不退化成 JSON），以及读路径 URL。
  在 Node 下需先替换全局 `Request`/`fetch` 再动态 import client，让单例抄到替换版。

校验：`workspace.py check frontend` 全绿（format / lint / typecheck / 19 tests /
build），`contract check` 通过。未改后端、migrations、认证授权代码，未加依赖。

## 自查与修正（2026-08-10）

提交前跑了一轮对抗式多维 review（permission / API-契约 / React / 约定），4 条
发现全部确认，已修：

1. `readSharedResourceVersionFile` 漏了 `parseAs: 'text'`——openapi-fetch 默认按
   JSON 解析，后端的 text/plain 纯文本会被 `JSON.parse` 抛 SyntaxError，**直接
   打不开文件预览**（恰好命中验收条件「点击预览文本内容」）。typecheck 和原测试都
   是绿的，因为契约里 200 类型是 `string`、mock 又只返回 JSON。补 `parseAs: 'text'`
   （与 `downloadArtifactFile` 用 `parseAs: 'blob'` 同理）。
2. 给 1 配了回归守卫：测试里让 `/files/content` 返回非 JSON 的 text/plain，断言
   拿到原始字符串。临时撤掉 `parseAs` 复跑确认该测试会红（`SyntaxError: ...import os`）。
3. `SharedResourcePanel` 创建成功弹了两次 toast（Modal 一次 + 面板 `onCreated` 一次），
   与 `CreateProjectModal` 单 toast 约定不符。去掉面板里那条，只保留刷新+跳转。

修正后 `workspace.py check frontend` 仍全绿（20 tests），`contract check` 通过。
