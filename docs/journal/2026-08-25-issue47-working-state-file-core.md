# issue47-working-state-file-core
- 状态：实现完成，`make check` 全量通过（backend 292 passed / frontend 全部组件测试 / contract check）
- 写入边界：`/home/scc/pb24000216/projects/107-workspace`（分支 `feat/47-working-state-file-core`，sole writer）
- 分支：`feat/47-working-state-file-core`
- 起点：`origin/main` `2594e1b`（#36 Ownership / Visibility 迁移已合并）
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

- 后端 `tests/integration/test_project_working_state.py`（15 个）：复制 / 建目录 / 压缩包安全场景
  （穿越、符号链接、加密、条目数与总量超限、非法 zip）/ 下载头 / 三类变更详情 / 放弃后版本不变与幂等 /
  PUBLIC 读者读写越权边界（读 404、写 403）。settings fixture 收紧上限以触发超限分支。
- 前端 `FileBrowser.test.tsx`（8 个）与 `VersionPanelChanges.test.tsx`（3 个）：上传成败分离状态、
  危险操作确认、只读无写入口、详情两侧展示、放弃需确认且刷新。
- 已知坑：antd Button 对两个中文字符自动插空格（"确 定"），断言须用 `\s*` 容忍。

## 未决 / 后续

- 浏览器 fresh evidence（桌面 / 375px / 键盘路径截图）尚未录制，需要起 dev 环境人工过一遍验收清单。
- 行级 diff、批量操作、搜索等仍在非目标清单内。
