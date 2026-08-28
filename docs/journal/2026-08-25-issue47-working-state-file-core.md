# issue47-working-state-file-core
- 状态：PR #73 评审修复与最终验收完成；`make check` 通过（backend 311 passed / 3 skipped；frontend 24 files / 134 tests；contract check）
- 写入边界：`/home/august/Projects/ustc_107/107-workspace-pr-73`（分支 `feat/47-working-state-file-core`，sole writer）
- 分支：`feat/47-working-state-file-core`
- 当前合并底座 / 评审起始 pushed head：`origin/main` `de6df22` / `feat/47-working-state-file-core` `246bc84`
- 开始：2026-08-25 +0800
- 关联：Issue #47；Parent #43；Depends on #36（已合并）；不承担 #20 Primer 迁移、#36 Ownership

## 意图与完成边界

补齐 `design.md` 中 Project Working State 文件管理 Core 的产品缺口：上传（含压缩包）、下载、建目录、
改名 / 移动、复制、删除确认、内容级未保存差异查看与放弃指定变更。已有后端能力直接复用，
仅新增确实缺失的最小 contract。

## 冻结决策

- **目录表示**：目录不是实体，靠文件路径前缀存在。`mkdir` 以 `<dir>/.gitkeep` 空占位文件实现，
  空目录因此可见、可保存进版本；同名文件冲突时返回 409。
- **压缩包**：只支持 zip。展开前整体校验（不做部分展开）：逐条目经 `normalize_path`
  （拒绝路径穿越 / 绝对路径），拒绝符号链接条目与加密条目；按声明的 file_size 预检单文件上限与
  解压后总量预算（防 zip 炸弹），读取时多读一字节暴露头部谎报。预算经组合根注入：
  `max_archive_total_bytes`（默认 128 MiB）与 `max_archive_entries`（默认 500），新增配置字段。
- **内容级 diff**：新增 `GET /changes/detail?path=`，返回基线（最近版本）与工作区两侧的 256 KiB 文本预览；
  新增时 previous 为空、删除时 current 为空。后端只存内容摘要，不做行级 diff。
- **放弃变更**：`POST /changes/discard {paths[]}`。added→删除工作区文件；modified→按基线 content_hash 覆盖回去；
  removed→按基线重建。全程复用基线 blob 摘要，不写新 blob、不改历史版本；无待放弃路径幂等跳过。
- **复制**：镜像 move 的守卫（src==dst、复制进自身子目录均拒绝），复用 content_hash 只增元数据行。
- **下载**：owner-scope 读（与 list/read 一致），octet-stream + RFC 6266 双文件名头（复用 runs.py 模式）。

## 新增 API（契约已同步）

- `GET /projects/{id}/files/download`、`POST .../files/copy`、`POST .../files/mkdir`、`POST .../files/archive`
- `GET /projects/{id}/changes/detail`、`POST /projects/{id}/changes/discard`

## 测试

- 后端 `tests/integration/test_project_working_state.py`（22 个）：复制（含真实源子树的自复制拒绝与
  缺失源区分）/ 空目录经目录路径移动、删除的可操作性 / 压缩包安全场景（穿越、符号链接、加密、
  条目数与总量超限、非法 zip，以及中央目录可读但成员内容 CRC 损坏）/ 下载头 / 三类变更详情 /
  放弃后版本不变与幂等 / PUBLIC 读者读写越权边界（读 404、写 403）。损坏成员在
  `archive.open` / `member.read` 抛出的 `zipfile.BadZipFile` 会转换为清晰的 422 validation
  响应；整个压缩包在任何写入前完成读取，因而同包中更早的合法成员也不会部分落盘。settings
  fixture 收紧上限以触发超限分支。
- 前端 `FileBrowser.test.tsx`（4 个）：多文件上传从上传中进入明确的成功 / 失败终态、压缩包整体
  拒绝原因、嵌套目录投影与目录路径危险操作后的可见刷新结果、具体只读 Project 不暴露写入口。
  `VersionPanelChanges.test.tsx`（4 个）：内容级差异两侧展示、放弃需确认且刷新、具体只读
  Project 不暴露保存 / 恢复 / 放弃入口、详情加载失败后可重试。
- 已知坑：antd Button 对两个中文字符自动插空格（"确 定"），断言须用 `\s*` 容忍。

## 2026-08-28 PR #73 final candidate evidence

- RED：新增行为测试后、修改 production source 前，定向 pytest 因
  `member.read` 抛出 `zipfile.BadZipFile: Bad CRC-32 for file 'corrupt.txt'` 失败；请求未得到
  validation 响应。GREEN：同一定向测试 `1 passed in 0.36s`；完整 working-state integration
  文件 `22 passed in 4.15s`。
- 最终 `make check`：workflow `15 tests`；backend `311 passed, 3 skipped in 31.35s`；
  frontend `24` files / `134` tests，format、lint、typecheck、build 均通过；OpenAPI 与 frontend
  types 一致。前端测试保留既有 jsdom `getComputedStyle(..., pseudoElt)` 与 React 19 / antd 5
  警告，未构成失败。
- 实际应用：标准 `make dev` 因同机另一个受管 worktree 已占用固定 `127.0.0.1:8000` 而无法并行；
  随后使用仓库同一 uvicorn / Vite 开发入口在 `8073` / `5175` 启动 final candidate，并以真实
  SQLite backend 创建 Project 与嵌套 `src/lib`、`docs` 文件。桌面树表正确展开嵌套目录，
  `docs` 目录的复制操作经 UI 成功生成 `docs-copy/guide.txt`。
- Chromium 375 px 验收：表格存在预期水平滚动（`scrollLeft` 达到 `187 / 187`），滚到最右后
  `src/main.py` 删除动作的 bounding box 为 `left 305.8 / right 329.8`，完整落在 375 px viewport
  内，可到达操作列。
- 键盘路径：从已选中的“版本”tab 连续 Tab 到“新增 README.txt”，Enter 打开 Change Detail。
  仅第一次 detail 请求在 HTTP 边界注入 503，Drawer 可见“无法加载变更详情”与“重试”；撤销注入
  后点击重试从真实 backend 展示“最近保存版本 / 当前工作区”及实际内容。关闭 Drawer 后焦点返回
  触发按钮“新增 README.txt”。
- 本仓库没有既有 screenshot evidence 目录；按 PR 模板约定未新增框架、未提交二进制。浏览器会话
  生成的本地截图为：桌面树表 `/tmp/omp-sshots-15691ad69b77fbe6.webp`、375 px 操作列
  `/tmp/omp-sshots-15691b1772f7fbe7.webp`、detail 错误 / 重试
  `/tmp/omp-sshots-15691b5f7c37fbe8.webp`、重试成功
  `/tmp/omp-sshots-15691b6ad777fbe9.webp`；发布 PR 时由 publish step 决定如何暴露。

## 未决 / 后续

- 行级 diff、批量操作、搜索等仍在非目标清单内。
