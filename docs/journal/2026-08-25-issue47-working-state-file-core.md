# issue47-working-state-file-core
- 状态：PR #73 单一剩余 blocker 已修复；`make check` 的测试 / lint / typecheck / build / contract 均通过，唯一 backend format finding 已修复并定向复验通过
- 写入边界：`/home/august/Projects/ustc_107/107-workspace-pr-73`（分支 `feat/47-working-state-file-core`，sole writer）
- 分支：`feat/47-working-state-file-core`
- 当前合并底座 / 本轮评审起始 pushed head：`origin/main` `de6df22` / `feat/47-working-state-file-core` `9a808898c62da69b2773420e31547027e13ee9c3`
- 开始：2026-08-25 +0800
- 关联：Issue #47；Parent #43；Depends on #36（已合并）；不承担 #20 Primer 迁移、#36 Ownership

## 意图与完成边界

补齐 `design.md` 中 Project Working State 文件管理 Core 的产品缺口：上传（含压缩包）、下载、建目录、
改名 / 移动、复制、删除确认、内容级未保存差异查看与放弃指定变更。已有后端能力直接复用，
仅新增确实缺失的最小 contract。

## 冻结决策

- **目录表示与保留名**：目录不是实体，靠文件路径前缀存在。`.gitkeep` 是 Project Working
  State 内部保留的空目录占位文件；只有 `mkdir` 可以物化 `<dir>/.gitkeep`。普通文本写入、
  multipart 上传和压缩包成员只要规范化后 basename 恰为 `.gitkeep`，就以 `ValidationFailed`
  返回 422；move / copy / delete / version restore / discard 仍可处理既有 marker。目标目录已有
  精确 marker 或任意 `<dir>/` 文件前缀时，重复 `mkdir` 在 blob / upsert / touch 前以
  `ConflictError` 返回 409；目录路径已有同名文件也保持 409。
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

- 后端 `tests/integration/test_project_working_state.py`（25 cases）：复制（含真实源子树的自复制拒绝与
  缺失源区分）/ 空目录经目录路径移动、删除的可操作性 / `.gitkeep` 普通 PUT 与 marker-only
  multipart 的 422 且无隐藏文件 / safe + marker 压缩包的 422 原子拒绝 / 重复 `mkdir`、隐式
  非空目录与同名文件的 409 且 listing 不变 / 压缩包安全场景（穿越、符号链接、加密、条目数与
  总量超限、非法 zip，以及中央目录可读但成员内容 CRC 损坏）/ 下载头 / 三类变更详情 / 放弃后
  版本不变与幂等 / PUBLIC 读者读写越权边界（读 404、写 403）。损坏成员在 `archive.open` /
  `member.read` 抛出的 `zipfile.BadZipFile` 会转换为清晰的 422 validation 响应；整个压缩包在
  任何写入前完成读取，因而同包中更早的合法成员也不会部分落盘。settings fixture 收紧上限以
  触发超限分支。
- 前端 `FileBrowser.test.tsx`（4 个）：多文件上传从上传中进入明确的成功 / 失败终态、压缩包整体
  拒绝原因、嵌套目录投影与目录路径危险操作后的可见刷新结果、具体只读 Project 不暴露写入口。
  `VersionPanelChanges.test.tsx`（4 个）：内容级差异两侧展示、放弃需确认且刷新、具体只读
  Project 不暴露保存 / 恢复 / 放弃入口、详情加载失败后可重试。
- 已知坑：antd Button 对两个中文字符自动插空格（"确 定"），断言须用 `\s*` 容忍。

## 2026-08-28 PR #73 final candidate evidence

- 本轮 RED（production source 修改前）：
  `test_reserved_gitkeep_basename_is_rejected_without_hidden_file` 的 PUT 与 multipart 两个 case
  都收到 200 而非 422，定向 pytest 为 `2 failed in 0.61s`，复现了用户输入可写入隐藏 marker。
- 本轮 GREEN：保留名 / archive 原子性 / mkdir 冲突三个行为测试（参数化后 4 cases）
  `4 passed in 0.87s`；完整 working-state integration 文件 `25 passed in 4.84s`。
- 单次 `make check`：workflow `15 tests`；backend `314 passed, 3 skipped in 31.56s`；
  frontend `24` files / `134` tests；backend / frontend lint、frontend format / typecheck / build、
  OpenAPI contract 均通过。该次命令唯一失败项是 backend format，精确指出本轮两个文件；
  按 formatter diff 修正后，定向
  `ruff format --check project_service.py test_project_working_state.py` 为 `2 files already formatted`。
  前端测试保留既有 jsdom `getComputedStyle(..., pseudoElt)` 与 React 19 / antd 5 警告，未构成失败。
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
