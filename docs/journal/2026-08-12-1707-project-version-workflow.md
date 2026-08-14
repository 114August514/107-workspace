# project-version-workflow

- 状态：完成
- 认领：unknown
- 上下文：issue #12
- 开始：2026-08-12 17:07 +0000

## 意图

完善 Project Version 浏览、比较与运行工作流（GitHub issue #12）。让 Project Version 从"保存后的历史记录"变成可浏览、可比较、可运行的不可变计算版本：Version 详情浏览、Version 文件预览、Version Diff、从指定 Version 发起 Run、Run History 展示源 Version。

## 预期改动

**后端：**
- `backend/migrations/versions/xxxx_run_project_version_column.py`（新建 Alembic 迁移）
- `backend/src/workspace107/infrastructure/db/tables.py`（`RunRow` 增加列）
- `backend/src/workspace107/domain/models.py`（`Run` 领域模型增加字段）
- `backend/src/workspace107/infrastructure/db/repositories.py`（`RunRepositoryImpl.add` / `_to_run` 贯穿字段）
- `backend/src/workspace107/application/run_service.py`（`create` / `rerun` 贯穿字段）
- `backend/src/workspace107/api/schemas.py`（`RunOut` 增加字段）
- `backend/src/workspace107/api/presenters.py`（`run_out` presenter 增加字段）
- `contracts/openapi.json`（重新生成）
- `frontend/src/api/schema.d.ts`（重新生成）

**前端：**
- `frontend/src/api/client.ts`（增加 `readVersionFile`）
- `frontend/src/pages/VersionDetailPage.tsx`（新建）
- `frontend/src/components/project/VersionFileBrowser.tsx`（新建）
- `frontend/src/components/project/VersionDiffPanel.tsx`（新建）
- `frontend/src/components/run/RunFromVersionModal.tsx`（新建）
- `frontend/src/App.tsx`（增加 `/versions/:versionId` 路由）
- `frontend/src/components/project/VersionPanel.tsx`（增加"查看详情"入口）
- `frontend/src/components/run/RunTable.tsx`（增加"版本"列）
- `frontend/src/components/run/RunSnapshotCard.tsx`（ID 改为可点击链接）

**测试：**
- `frontend/tests/component/VersionDetailPage.test.tsx`（新建）
- `frontend/tests/component/VersionDiffPanel.test.tsx`（新建）
- `frontend/tests/component/RunFromVersionModal.test.tsx`（新建）
- `frontend/tests/component/RunTable.test.tsx`（新建）
- `backend/tests/unit/application/test_run_version_fields.py`（新建）

## 仓外副作用

Alembic 迁移修改 `runs` 表 schema：增加 `project_version_id` 和 `project_version_label` 两列，从 `run_snapshots.payload` JSON 回填，收紧为 NOT NULL + 索引。

## 回退方式

`cd backend && uv run alembic downgrade -1` 回退迁移；前端变更 `git revert <commit>`。

## 验收

`make check`

## 禁区

- 不动 Worker/Slurm 执行路径
- 不动 #10 的文件导入工作
- 不加依赖

---

# 执行计划正文

## Context

Issue #12 要求让 Project Version 从"保存后的历史记录"变成可浏览、可比较、可运行的不可变计算版本。当前后端 API 完整支持 Version 详情 (`GET /api/v1/versions/{version_id}`)、Version 文件读取 (`GET /api/v1/versions/{version_id}/files/content`)、Version Diff (`GET /api/v1/versions/{version_id}/diff?base=`)，前端 API client 中 `getVersion` 和 `diffVersions` 也已存在，但**零组件调用它们**。前端缺少：Version 详情入口和组件、Version 文件浏览、Version Diff 视图、从指定 Version 发起 Run 的入口、Run History 中对 Project Version 的展示。

唯一的后端缺口：`RunOut` 不包含 `project_version_id`（只在 `RunSnapshotOut` 中），导致 Run 列表无法直接展示版本信息。

## Approach

分六个行为组（A-F），按依赖顺序排列。A 必须先完成（前端类型依赖契约重新生成）。B 独立于 A。C/D/E 依赖 A+B。F 依赖所有前置完成。步骤标注 `[独立]` 的可在同组内并行。

### A. 后端：RunOut 增加 project_version_id + project_version_label（Run History Version 可追溯性）

复用 `compute_plan_id` 的冗余列模式——同样从快照 JSON 里冗余到 `runs` 表，原因相同（快照是 JSON，无法索引/查询）。同时冗余 `project_version_label`，因为 label 不可变且 Run History 需要人类可读展示，避免前端为每行 Run 额外请求 version detail。

1. **`[独立]` 新建 Alembic 迁移** `backend/migrations/versions/xxxx_run_project_version_column.py`：复制 `820b10c622f1_run_compute_plan_column.py` 的三步模式——加可空列 → 回填 → 收紧为 NOT NULL + 创建索引。`down_revision` 指向 `de1e5e1dd6ab_notification_center`（当前最新）。回填走 Python 解析 JSON：`SELECT r.id, s.payload FROM runs r JOIN run_snapshots s ON s.id = r.snapshot_id`，取 `data["project_version_id"]` 得到 version_id，再 `SELECT label FROM project_versions WHERE id = :version_id` 获取 label。两列同时回填。

2. **`RunRow` 增加列** (`backend/src/workspace107/infrastructure/db/tables.py` L238-261)：在 `compute_plan_id` 后增加 `project_version_id: Mapped[str] = mapped_column(ID, index=True)` 和 `project_version_label: Mapped[str] = mapped_column(String(256))`。注释说明冗余原因同 `compute_plan_id`。

3. **`Run` 领域模型增加字段** (`backend/src/workspace107/domain/models.py` L297-322)：在 `compute_plan_id` 后增加 `project_version_id: str` 和 `project_version_label: str`。

4. **`RunRepositoryImpl` 贯穿字段** (`backend/src/workspace107/infrastructure/db/repositories.py`)：
   - `add` (L737-758)：`t.RunRow(...)` 增加 `project_version_id=run.project_version_id, project_version_label=run.project_version_label`
   - `_to_run` (L1366-1385)：增加 `project_version_id=row.project_version_id, project_version_label=row.project_version_label`

5. **`RunService.create` 贯穿字段** (`backend/src/workspace107/application/run_service.py` L351-362)：`Run(...)` 构造增加 `project_version_id=snapshot.project_version_id, project_version_label=result.project_version.label`（`snapshot` 在 L328 已创建，`result.project_version` 在 L322 已断言非空）。

6. **`RunService.rerun` 贯穿字段** (`backend/src/workspace107/application/run_service.py` ~L416)：从 `source_snapshot.project_version_id` 传入 `project_version_id`，从已查出的 `project_version`（L410 附近）传入 `project_version_label`。

7. **`RunOut` schema 增加字段** (`backend/src/workspace107/api/schemas.py` L340-358)：在 `snapshot_id` 后增加 `project_version_id: str` 和 `project_version_label: str`。

8. **`run_out` presenter 增加字段** (`backend/src/workspace107/api/presenters.py` L222-249)：`s.RunOut(...)` 增加 `project_version_id=run.project_version_id, project_version_label=run.project_version_label`。

9. **重新生成契约**：`make contract`（后端导出 OpenAPI → 前端生成 `schema.d.ts`）。这会让前端类型自动获得 `RunOut.project_version_id` 和 `project_version_label`。

### B. 前端 API client 补全

10. **`[独立]` 增加 `readVersionFile`** (`frontend/src/api/client.ts`，在 `diffVersions` 之后 L377)：
```typescript
readVersionFile: async (versionId: string, path: string): Promise<FileContent> =>
  unwrap(
    await http.GET('/api/v1/versions/{version_id}/files/content', {
      params: { path: { version_id: versionId }, query: { path } },
    }),
  ),
```
`FileContent` 类型已存在于 `types.ts`（`Schemas['FileContentOut']` = `{ path, content, truncated }`）。schema.d.ts 中路径已存在（L715）。

### C. 前端：Version 详情与文件浏览

11. **新建 `VersionDetailPage`** (`frontend/src/pages/VersionDetailPage.tsx`)：
    - 路由参数：`versionId`（`useParams`）
    - 数据加载：`api.getVersion(versionId)` → `ProjectVersionDetail`（含 `files: ProjectVersionFileOut[]`）
    - 同时加载所属 Project 和 Workspace（从 `version.project_id` → `api.getProject` → `api.getWorkspace`）以驱动面包屑和权限判断
    - 页面结构（复用 `PageHeader` + `Stack` + `Card` + `Tabs`）：
      - PageHeader：面包屑 [首页 → Workspace → Project → Version v{sequence}]，标题 `v{sequence}`，描述 = version.message
      - Descriptions：创建人 `created_by`、创建时间 `created_at`、文件数 `file_count`、总大小 `total_size`（用 `formatBytes` / `formatTime`）
      - Tabs：
        - "文件" → `VersionFileBrowser` 组件（只读）
        - "版本比较" → `VersionDiffPanel` 组件
      - 操作区（PageHeader actions）：
        - "运行此版本" 按钮（gated by `can(workspace, 'run.submit')`）→ 打开 `RunFromVersionModal`
        - "恢复到此版本" 按钮（gated by `can(workspace, 'project.content.write')`）→ Popconfirm → `api.restoreVersion(versionId)` → `navigate(`/projects/${projectId}`)`
        - "派生" 按钮（NOT gated，同 VersionPanel 现有逻辑）→ 打开 `ForkModal`
    - Viewer 可见性：所有操作按钮按 `can()` 隐藏，Viewer 只能看到文件和 Diff

12. **新建 `VersionFileBrowser`** (`frontend/src/components/project/VersionFileBrowser.tsx`)：
    - Props：`{ versionId: string }`
    - 数据：`api.getVersion(versionId)` 获取文件列表（`ProjectVersionFileOut[]` = `{ path, size, content_hash }`）
    - 渲染：antd `Table`，列 `[path, size (formatBytes)]`，行点击打开只读 `Drawer`
    - 只读文件预览 `Drawer`：调用 `api.readVersionFile(versionId, path)` → `FileContent`（`{ content, truncated }`），用 `Typography.Paragraph` 显示文本，`truncated` 时显示 Alert 提示"内容已截断"
    - **不提供任何编辑入口**——无写入按钮、无保存按钮。Drawer 标题显示文件路径 + "只读" Tag
    - 复用 `FileBrowser.tsx` 中 Drawer 的视觉模式（antd Drawer + Typography），但去掉所有写操作

13. **新建 `RunFromVersionModal`** (`frontend/src/components/run/RunFromVersionModal.tsx`)：
    - Props：`{ open: boolean; versionId: string; versionLabel: string; projectId: string; defaultRunConfigurationId: string | null; workspace: Workspace | undefined; onClose: () => void; onSubmitted: (run: Run) => void }`
    - 数据：`api.listRunConfigurations(projectId)` → `RunConfiguration[]`
    - 默认选择：如果 `defaultRunConfigurationId` 匹配列表中的某项，自动选中；否则选中第一个（如果有的话）
    - UI 结构：antd `Modal` + `Form`：
      - `Select` 选择 Run Configuration（默认选中 default config）
      - 可选 `Input` 填写 Run 名称
      - Preflight 区域：选中 configuration 后调用 `api.preflight(projectId, { run_configuration_id, project_version_id: versionId })`，展示结果（复用 `SubmitRunModal` 的 preflight 展示逻辑——secret 引用、环境变量、算力信息）
      - 提交按钮：`api.createRun(projectId, { run_configuration_id, project_version_id: versionId, name }, idempotencyKey)`
    - **关键差异 vs 现有 `SubmitRunModal`**：`RunDraft` 中显式传入 `project_version_id: versionId`，而非省略让后端默认取最新版本。这确保 Run 绑定用户选择的确定版本。
    - 无可用 Run Configuration 时：显示 Alert 提示"请先创建运行方案"，禁用提交按钮
    - 复用 `newIdempotencyKey()` 和 `ApiError` 错误处理模式

14. **新增路由** (`frontend/src/App.tsx` L33-39)：在 `runs` 路由后增加：
```tsx
<Route path="/versions/:versionId" element={<VersionDetailPage key={username} />} />
```
导入 `VersionDetailPage`。

15. **VersionPanel 增加详情入口** (`frontend/src/components/project/VersionPanel.tsx` L92-143)：在版本表 `columns` 的 `actions` 列中，在"恢复"和"派生"之前增加"查看详情"按钮（`type="link" size="small"`，`onClick={() => navigate(`/versions/${version.id}`)}`）。此按钮不受权限限制——所有能看见版本列表的用户都能查看版本详情。

### D. 前端：Version Diff 视图

16. **新建 `VersionDiffPanel`** (`frontend/src/components/project/VersionDiffPanel.tsx`)：
    - Props：`{ projectId: string; currentVersionId: string; currentVersionLabel: string }`
    - 数据：`api.listVersions(projectId, { page: 1 })` 获取版本列表（用于选择对比目标），`api.diffVersions(currentVersionId, baseVersionId)` 获取差异
    - UI 结构：
      - 顶部：antd `Select` 选择"对比基准版本"（排除当前版本自身，按 sequence 降序排列）。默认选中当前版本的前一个版本（`sequence` 最接近且小于当前版本的项）
      - 无前序版本时（当前是 v1）：显示空状态 Alert "这是第一个版本，没有可比较的历史版本"
      - Diff 结果：antd `Table`，列 `[change (Tag), path]`。`change` 列用 `CHANGE_LABEL` 映射（已在 VersionPanel 中定义，提取为共享常量或直接内联同样的 `Record<ChangeKind, { text, color }>`）
      - Diff 为空数组时：显示 Alert "两个版本内容完全相同"
    - 错误处理：`diffVersions` 返回 400 时（如跨 Project 比较，正常不会触发但防御性处理）显示错误 Alert

### E. 前端：Run History 展示 Version

17. **RunTable 增加 Version 列** (`frontend/src/components/run/RunTable.tsx`)：
    - 在"名称"列后增加"版本"列：`dataIndex: field<Run>('project_version_label')`，渲染为 `<Link to={`/versions/${run.project_version_id}`}>{run.project_version_label}</Link>`
    - `project_version_id` 和 `project_version_label` 都来自步骤 A 增加的 `RunOut` 字段。label 提供可读展示（如 `v3`），id 提供跳转目标。

18. **RunSnapshotCard 优化** (`frontend/src/components/run/RunSnapshotCard.tsx` L26)：将 `<Typography.Text code>{snapshot.project_version_id}</Typography.Text>` 改为 `<Link to={`/versions/${snapshot.project_version_id}`}>{snapshot.project_version_id}</Link>`，保持 raw ID 显示但可点击跳转。（不改为 label，因为 snapshot 不含 label，且这是复现信息展示，raw ID 更精确。）

### F. 测试

19. **`[独立]` 前端组件测试** (`frontend/tests/component/`)：
    - `VersionDetailPage.test.tsx`：mock `api.getVersion` 返回带文件的 `ProjectVersionDetail`，渲染页面，断言文件列表、信息描述可见
    - `VersionDiffPanel.test.tsx`：mock `api.diffVersions` 返回 `[{change:'added',path:'new.py'},{change:'modified',path:'main.py'}]`，断言表格行；mock 返回空数组，断言空状态 Alert
    - `RunFromVersionModal.test.tsx`：mock `api.listRunConfigurations` 返回含默认配置的列表，断言默认选中；mock `api.createRun` 断言 `project_version_id` 被传入
    - `RunTable.test.tsx`：mock runs 含 `project_version_id` 和 `project_version_label`，断言列渲染和链接
    - Viewer 可见性测试：mock workspace capabilities 不含 `run.submit`，断言"运行此版本"按钮不渲染
    - 测试基础设施：用 `@testing-library/react` 的 `render`，mock `api` 模块用 `vi.mock('../../api/client', ...)`，用 `MemoryRouter` 包裹路由依赖组件。环境设置为 `jsdom`（需在 vite.config.ts test 中改 `environment: 'jsdom'` 或在测试文件中用 `// @vitest-environment jsdom` 注释）

20. **`[独立]` 后端测试** (`backend/tests/unit/application/`)：
    - 在现有测试模式中增加 `test_run_version_fields.py`：验证 `RunService.create` 产生的 `Run` 包含正确的 `project_version_id` 和 `project_version_label`
    - 验证 `run_out` presenter 输出包含这两个字段

## Critical files & anchors

| File | Region | Why |
|---|---|---|
| `backend/src/workspace107/infrastructure/db/tables.py` L238-261 | `RunRow` | 增加 `project_version_id` + `project_version_label` 列 |
| `backend/src/workspace107/application/run_service.py` L328-362 | `create` 方法 | Run 构造时设置 version 字段 |
| `backend/migrations/versions/820b10c622f1_run_compute_plan_column.py` | 迁移模板 | 复制此模式做新迁移 |
| `frontend/src/components/project/VersionPanel.tsx` L92-143 | 版本表 columns | 增加"查看详情"入口 |
| `frontend/src/components/run/SubmitRunModal.tsx` L32-77 | preflight + submit 流程 | `RunFromVersionModal` 的参考实现 |

## Verification

1. **后端迁移**：`cd backend && uv run alembic upgrade head` —— 确认迁移成功，`runs` 表新增两列且已回填
2. **契约同步**：`make contract` —— 确认 `contracts/openapi.json` 和 `frontend/src/api/schema.d.ts` 更新且 `make check` 的 contract-check 通过
3. **后端测试**：`cd backend && uv run pytest -q` —— 确认新增测试和全部已有测试通过
4. **前端测试**：`cd frontend && pnpm run test --run` —— 确认组件测试通过
5. **前端构建**：`cd frontend && pnpm run build` —— 确认生产构建无错误
6. **端到端手动验证**（`make dev` 启动前后端）：
   - 在 Project 页面 → 版本 Tab → 点击某版本"查看详情" → 进入 Version 详情页 → 确认文件列表、信息描述、操作按钮显示正确
   - 在 Version 详情页 → 点击某文件 → Drawer 显示只读内容，无编辑入口
   - 在 Version 详情页 → "版本比较" Tab → 选择基准版本 → 确认 Diff 表格显示 added/modified/removed
   - 在 Version 详情页 → 点击"运行此版本" → Modal 打开 → 确认默认 Run Configuration 被选中 → 提交 → 跳转到 Run 页面 → 确认 Run snapshot 中 `project_version_id` 匹配
   - 在 Project 页面 → Run 历史 Tab → 确认每行显示版本标签（如 `v3`）且可点击跳转到 Version 详情
   - 切换为 Viewer 用户 → 确认"运行此版本"和"恢复"按钮不可见，但"查看详情"和"派生"可见
7. **完整检查**：`make check` —— 全部步骤通过

## Assumptions & contingencies

- **假设**：`RunOut` 增加 `project_version_id` + `project_version_label` 是可接受的契约扩展（非破坏性，只增字段）。如果 reviewer 认为不应冗余 label，回退为只加 `project_version_id`，RunTable 中显示"版本详情"链接而非 label。
- **假设**：Version 详情页用独立路由 `/versions/:versionId` 而非 Project 页面内的子 Tab 或 Modal。如果 reviewer 更倾向 inline 展示，改为在 VersionPanel 中用 Drawer 展示详情——但路由方案更利于深度链接和 Run History 跳转。
- **假设**：前端测试环境从 `node` 改为 `jsdom`（组件测试需要 DOM）。在 `vite.config.ts` 的 `test.environment` 改为 `'jsdom'`，或在每个组件测试文件头加 `// @vitest-environment jsdom`。选择后者以避免影响现有 `node` 环境的纯函数测试。
- **假设**：`RunFromVersionModal` 与现有 `SubmitRunModal` 保持独立而非重构合并。两者差异在于 `project_version_id` 是否显式传入和默认 configuration 选择逻辑。如果后续需要合并，提取共享的 preflight 展示组件即可，但本次不做。
- **contingency**：如果迁移回填时发现某些 Run 的 snapshot 已被清理（`run_snapshots` 行不存在），跳过这些行并记录警告——但根据 GR-202 快照只 INSERT 不 DELETE，正常不会发生。
