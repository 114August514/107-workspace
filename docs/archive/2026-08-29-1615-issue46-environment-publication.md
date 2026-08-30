# issue46-environment-publication

- 状态：已完成并归档（Issue #46 post-merge closure evidence）
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

## Post-merge closure：本机真实 Apptainer SIF publication

2026-08-30 在 `origin/main` 提交 `c989f6d1324b893c63923b20f2c58164b5646a7c`
（#85 已合并）上完成 #46 剩余的真实成功证据。此前“当前机器未安装 Apptainer”的记录
保留为当时事实；本节是安装 Apptainer 后的新证据，不改写旧观察。

### 环境与输入

- 主机：Arch Linux x86_64；`uname -m` 为 `x86_64`。
- CLI：Arch package `apptainer 1.5.3-2`，`/usr/bin/apptainer version` 为 `1.5.3`，
  实际路径 `/usr/bin/apptainer`。
- OCI 来源：Docker Hub 官方 `library/alpine` 的固定 multi-architecture index
  `sha256:4bcff63911fcb4448bd4fdacec207030997caf25e9bea4045fa6c8c44de311d1`；
  使用
  `docker://docker.io/library/alpine@sha256:4bcff63911fcb4448bd4fdacec207030997caf25e9bea4045fa6c8c44de311d1`
  和 `--arch amd64 --disable-cache` 构建 SIF。任务建议值末尾多一个 `f`，共有 65 个十六
  进制字符，Apptainer 以 `invalid checksum digest length` 拒绝；去掉多出的末尾字符后，
  SIF 内 `org.opencontainers.image.base.digest` 和 `from` label 均回报上述固定 digest。
- 上传 SIF：3,719,168 bytes；
  SHA-256 `a2954245e29538cd18cb7edbd6d06ef58fa8d4743324bf739261acb4d4bdc695`。
  独立执行 `/usr/bin/apptainer inspect --json` 成功，标准
  `org.label-schema.build-arch` 为 `amd64`，构建工具 label 为 Apptainer `1.5.3`。

### 真实 API 与 background processor

- 使用隔离 SQLite database、storage 与 Apptainer cache；配置
  `WORKSPACE107_AUTH_MODE=dev`、
  `WORKSPACE107_ENVIRONMENT_PUBLICATION_INTERVAL_SECONDS=0.1`，先执行 Alembic
  `upgrade head` 和 demo seed，再启动真实 Uvicorn factory app。没有 monkeypatch、CLI double、
  processor 直调或伪 SIF。
- 以 `X-User: student` 对 `env_demo_python_2026` 提交真实 multipart
  `POST /api/v1/catalog/environments/env_demo_python_2026/publication-attempts/apptainer-sif`。
  HTTP 返回 `202`，attempt `evpa_44938a8dbe7e4ed78df2` 初始状态为 `pending`。
- Uvicorn lifespan 内的 background loop 随后把 attempt 更新为 `succeeded`，
  `version_id=ev_0910adbd8b7443d2974a`，没有直接调用 processor。版本标签
  `issue46-alpine-3.22.1-amd64` 在该 Environment 下计数为 `1`。
- Version 为 `runtime_kind=apptainer_sif`、`availability=available`；
  definition 的 `sha256` 与 `locator` 均为上传 SIF SHA-256，`size=3719168`，
  `architecture=x86_64`、`launcher_module=apptainer/1.4.5`、
  `exec_policy=apptainer_exec_v1`。`definition_hash` 为
  `c2933281d52c65e95389580ac39027c736f229a969108efe7dd421ecbbe1a3b7`。
- validation evidence 为 `validator=apptainer_inspect_v1`、`cli=/usr/bin/apptainer`、
  `inspect_architecture=amd64`、规范化 `architecture=x86_64`、
  `byte_size=3719168`；`inspect_sha256` 为
  `d7b697984c127c8c57d60f9df13ffde1dfcb667c0ae62ce9f43cf0e3963f8134`，
  `canonical_definition_sha256` 与 Version `definition_hash` 相同。

### CAS、refresh 与不可变性

- CAS 文件位于内容寻址 shard
  `storage/blobs/a2/a2954245e29538cd18cb7edbd6d06ef58fa8d4743324bf739261acb4d4bdc695`。
  `cmp` 证明它与上传 SIF byte-for-byte 相同；重新计算 SHA-256 仍为
  `a2954245e29538cd18cb7edbd6d06ef58fa8d4743324bf739261acb4d4bdc695`，
  对 CAS 文件再次执行真实 `apptainer inspect --json` 成功且 build arch 仍为 `amd64`。
- 两次真实 availability refresh 均保持 `available`，reason 更新为
  `refresh_validated`。refresh 前后以 canonical JSON 计算的不可变字段
  `definition`、`definition_hash`、`execution_spec`、`validation_summary` 和
  `validation_evidence` 整体 SHA-256 都是
  `3e173cdf28aea6a12a51f515b6b3a7cc7b2f8d741cd4d72a55d68db9a6fb2f60`；
  definition、evidence 与内容 hash 未漂移。

### 证据边界与清理

该证据证明 Arch Linux x86_64、Apptainer `1.5.3` 的本机真实 SIF publication 闭环；
它不证明 live 107 的 `apptainer/1.4.5` module、共享挂载、Workspace UID/GID、独立 Worker
或 Slurm 执行，这些端到端边界仍属于 #7。Uvicorn 已停止；隔离 database、storage、cache、
SIF、其他 `/tmp` 材料和本 worktree 临时 Python environment 均已删除。仓库未保留 SIF、
日志、数据库或 secret。
