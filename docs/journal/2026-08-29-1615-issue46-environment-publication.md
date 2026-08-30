# issue46-environment-publication

- 状态：最终候选（未提交、未推送、未建 PR）
- 认领：August（本 worktree 唯一文件与 Git writer）
- 上下文：Issue #46；worktree `/home/august/Projects/ustc_107/107-workspace-46-environment`；branch `feat/46-environment-publication`
- 开始：2026-08-29 16:15 +0800

## 意图

把旧的 `image` + 任意 `setup_command` Environment Version 破坏性切换为 ADR 0004 的 `modules` / `apptainer_sif` 持久 publication contract，并迁移所有 API、Run 和 UI 消费者。

## 数据与迁移事实

用户明确授权开发期 destructive reset：没有 Environment Version 数据必须保留。migration upgrade 删除旧 Version 及依赖的 Run、Run Snapshot、Run Configuration、Run Event、Artifact、redaction 和 idempotency 开发数据后建立新 schema；它保留全部 Activity 与 Notification 历史。down 同样只恢复旧 Environment Version schema 形状，不恢复被删除的版本或执行数据。

## 平台权威

`docs/references/platform/` 的当前 PDF 是 Ubuntu 24.04.3、Environment Modules、共享 `/public`/`/home`、无 sudo 与支持 module 清单的事实来源。产品 contract 采用用户冻结的精确清单；V1 runtime allowlist 排除 VS Code developer module。不会访问 live 107。

## 范围与非目标

- 范围：canonical definition/digest；modules allowlist/order/profile/activation；CAS SIF 字节与真实 Apptainer CLI 验证（包括实际架构元数据与最终真实成功发布证据）；durable attempt；availability evidence；精确 Run Snapshot/执行 spec；Environment UI publication 与证据状态；OpenAPI/generated types。
- 非目标：通用 provider/adapter/validator registry、任意组合图、任意 setup shell、用户 modulefiles、live 107、真实 Workspace UID/GID/共享挂载/独立 Worker/Slurm REST/凭据与执行接缝。只有这些下游集成属于 #7。

## 证据计划

1. 行为测试先证明旧 contract 不满足新 runtime/state/immutability/atomicity/authorization/recovery/allowlist/SIF CLI/availability/no-fallback contract。
2. migration upgrade/down/up；targeted backend 与 PostgreSQL（若本地依赖可用）。
3. contract sync/check；frontend Environment 与 Run affected tests/typecheck/build。
4. 本地真实 HTTP → durable processor smoke：modules 成功；SIF 在本机真实 CLI 可用时成功，否则明确失败。
5. `make check`，浏览器在 runtime 可启动时验证 affected surface。

## 仓外副作用

无；不 push、不 commit、不建 PR。

## 回退方式

丢弃未提交 Environment worktree candidate；不改 main 与 PR #75。

## 验收

上述证据与 `make check`；所有限制如实记录。

## 禁区

- 不改 PR #75 branch，不 stack Shared Resource PR。
- 不扩张 #7 或 live 107。
- 不新增依赖或通用 runtime abstraction。

## 候选结果与 fresh evidence

- `make check`：通过；backend、frontend、workflow 与生成契约检查均通过。
- backend 全量：329 passed / 3 skipped；最终 Environment publication targeted：3 passed。
- frontend affected：Environment publication/pending/evidence、Run exact-version surface 通过；typecheck 与 production build 通过。
- migration：临时 SQLite 实际执行 fresh upgrade head → downgrade `f42a9c7e1d30` → upgrade head，通过；临时数据库已删除。
- publication：真实 HTTP 创建 Attempt；Modules 候选从可恢复的 `processing` 原子发布一个 Version；allowlist 失败与 SIF CLI 不可用均无 Version。当前机器 `which apptainer` 退出 1，因此没有宣称本地 SIF 成功。
- contract：`make contract` 生成 OpenAPI 与 TypeScript，最终 contract check 由 `make check` 通过。
- browser：启动真实 Vite 与 API，并加载 demo App；受本机 8000 端口占用与请求改写后的 Environment 路由重定向影响，未取得 Environment route 的可信视觉证据。组件行为测试覆盖该页面的 loading/error、pending、validation 与 availability 状态；不宣称浏览器 Environment 详情通过。
- 未运行 PostgreSQL：本地未启动专用 PostgreSQL 依赖；SQLite migration roundtrip 与 repository/application tests 是本候选数据库证据边界。

Owned browser/API 进程、临时 DB 与存储目录均已停止或删除。未访问 live 107；未 commit、push 或创建 PR。

## Focused verification remediation

- SIF identity remains the immutable CAS hash/locator. `StoragePort.resolve_blob_path` rehashes the CAS file and returns the scheduler-visible path only immediately before submission. The external CLI double now returns realistic Apptainer 1.4 JSON with `org.label-schema.build-arch=amd64`; the processor canonicalizes it to `x86_64`, while an ARM result fails without creating a Version. The x86 publication → Run test still proves rendered `apptainer exec` uses the real CAS file path, not the bare hash.
- Migration reset no longer deletes Activity or Notification rows. A fresh predecessor fixture proves both histories survive upgrade, Environment Versions are reset, and downgrade/upgrade completes.
- Authorized repository-filtered attempt history/list hydrates the Environment panel after reload; pending/processing attempts are lifecycle-polled and failed reasons remain visible.
- The existing Primer panel now supports both ordered Modules and multipart Apptainer SIF input with fixed `x86_64`; frontend behavior covers hydrated failure and SIF request state.
- One explicit availability repository update and concrete refresh processor revalidate Modules allowlist or SIF CAS/CLI, update only availability/reason/detail/checked time, and return a new projection. The SIF-path test deletes the validated blob, refreshes to unavailable without changing definition/evidence, and confirms preflight consumes the refreshed state without fallback.
- Final `make check`: backend 338 passed / 3 skipped; frontend 25 files / 148 tests; workflow, Ruff, formatting, frontend lint/typecheck/build, OpenAPI/generated-type check all passed.
- Architecture remediation reverify：Environment publication 5 passed；targeted Ruff 与 contract check 通过；ARM inspect 成功返回但发布失败且无 Version，`amd64` 成功路径继续到达真实 CAS scheduler path。
- Targeted independent re-review：PASS；无剩余 finding。
- Honest limits：未用真实 Apptainer CLI 做成功发布；这项证据仍由 #46 负责，不转交 #7。#7 只负责下游 Workspace 身份、共享挂载、独立 Worker 与 Slurm 执行接缝。未运行专用 PostgreSQL；未取得 Environment route 的可信浏览器视觉证据；未访问 live 107。
