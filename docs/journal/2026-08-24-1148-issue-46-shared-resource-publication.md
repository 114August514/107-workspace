# issue-46-shared-resource-publication

- 状态：第一段完成；smoke、verification、独立 review 与 targeted re-review 均 PASS
- 认领：August（sole writer）
- 上下文：Issue #46 第一段；`/home/august/Projects/ustc_107/107-workspace-46`，`feat/46-asset-validation`
- 开始：2026-08-24 11:48 +0800

## 意图
完成 Shared Resource 发布/校验的持久异步闭环。上传请求只创建并返回独立的
`SharedResourcePublicationAttempt`；失败 attempt 永远不是 Version；只有处理期校验成功才在
同一数据库事务中创建一个不可变 `SharedResourceVersion` 及文件行。中断任务可安全恢复，
重复处理不产生重复 Version。

冻结语义：本开发分支不保留旧的同步发布 API 或字段，也不迁移旧数据；允许 destructive
development cutover。现有 content-addressed blob storage、Version 不可变性、Owner、
repository-layer authorization filtering 与 USE Grant 边界保持不变。

## 预期改动
- 数据库迁移、Shared Resource domain/repository/application/API 与独立 processor runtime
- FastAPI OpenAPI source 导出的 `contracts/openapi.json` 与生成的前端 schema
- Shared Resource 上传 UI：展示 pending/succeeded/failed attempt，不再假定上传即发布
- 行为测试：授权创建/读取、处理期有效校验、持久失败且无 Version、中断恢复、重复处理幂等、
  原子发布与现有内容读取/不可变行为
## 仓外副作用
无。

## 回退方式
在未提交状态按本 journal 的文件清单逐项恢复；提交后使用非破坏式 `git revert <commit>`。
数据库迁移使用现有 Alembic downgrade 链；开发数据明确可丢弃。

## 验收
- RED：新增 observable publication-attempt contract / processing behavior tests 在实现前按预期失败
- targeted backend domain/repository/API/processor/migration tests
- `make contract` / `make contract-check`
- affected frontend tests、typecheck/build
- 本地真实 HTTP 上传 → 独立 processor → 成功 Version（另覆盖 processing validation failure）
- broadest justified repository check：`make check`

## Fresh evidence
- RED：新 publication tests 首次运行得到 5 个预期失败（旧端点返回 201/Version）。
- targeted backend：Shared Resource publication/service 24 passed；resource integration 54 passed。
- 迁移：临时 SQLite 执行 upgrade head → downgrade `4d7a2f91c3e5` → upgrade head 成功。
- contract：`make contract` 后 `make contract-check` 通过。
- frontend：publication API/modal 9 passed；`make check-frontend` 通过；typecheck 与 build 通过。
- smoke：真实 Uvicorn + SQLite + LocalStorage，HTTP POST 返回 202/pending；
  独立 lifespan processor 转为 succeeded，发布恰好一个 `shrv_*` Version，manifest/blob 摘要一致。
- broad：`make check-backend`（276 passed, 3 skipped）与最终 `make check` 均通过。
- browser：真实页面与发布 Dialog 在 1280×900 加载并可选择文件；因验证时用请求改写绕开被占用的
  8000 端口，multipart 请求在该改写层报网络错误，不把这一段宣称为端到端 UI 成功；
  modal pending/succeeded/failed 行为由 component test 覆盖。

## Independent review remediation
- 迁移 authority：保留明确获准的 destructive development cutover；迁移文案不再把授权归于
  Issue 本身，并明确 `shared_resource_version_files` 与 `shared_resource_versions` 的全部旧行会删除，
  当前授权说明无数据需要保留。
- 前端 polling：每次只安排一次可取消查询；关闭或卸载会 abort 当前请求并清除后续 timer。
  attempt ID 保存在当前浏览器 session、按 Shared Resource 隔离；重新打开后由用户点击“继续查询结果”，
  不再上传 candidate。成功/失败终态清除保存的 ID。
- Compose：API service 显式传入 publication interval `1.0` 和 recovery `300.0` 默认值，
  与 `.env.example` 的说明一致；`docker compose config` 已解析出两项。
- ingress finding：不接受扩大。授权、multipart/schema、路径安全、重复路径与大小是 candidate
  被接受前的同步边界，422 raw request 不创建 attempt；被接受后的 CAS blob 存在性、hash、size
  才由异步处理器校验，校验失败持久化。
- multi-worker finding：不把 defensive row locks 宣称为多 worker exactly-once。当前 authority 是
  单 API 实例中的单 publication loop；保证 separately committed claim 的 restart recovery、
  串行 terminal idempotency 和单次 loop 不自我 reclaim。未来多 replica 或长耗时 validator
  需要单独的 fencing/heartbeat 设计，本 slice 不提供该契约。

## Remediation evidence
- publication modal/API tests：11 passed；覆盖 pending 时关闭、AbortSignal、无后续 poll、
  卸载后重开并复用 attempt ID、无第二次 upload。
- frontend `typecheck` 与 production `build` 通过。
- backend publication/service targeted tests：24 passed。
- `make contract-check` 通过。
- `docker compose --project-directory . -f deploy/compose.yaml config` 通过并显示默认值
  `1.0` / `300.0`。

## Targeted re-review lifecycle fix
- `PublishVersionModal` 以 `resourceId` 作为内部 publication state 的 React key；路由复用组件并切换
  Shared Resource 时，旧资源 effect 会先 cleanup/abort，随后为新资源重新初始化 form、feedback、
  polling 与该资源自己的 sessionStorage attempt ID。切换不会删除其他资源的保留 ID。
- navigation rerender behavior test：A polling 后切到 B 会停止 A；B 只读取并在失败后清除 B key；
  A key 保留，返回 A 后可继续读取 A，整个过程无 candidate upload。modal exact tests 5 passed，
  随后 frontend typecheck 与 production build 通过。

## Final cleanup
- 最终 targeted independent review：PASS；此前 smoke 与 verification 也为 PASS。
- resource-isolation modal test 保证 A → B → A 导航只读取/清除当前资源的 attempt key，
  返回 A 可恢复且不二次上传；exact modal tests 5 passed。
- 最新 `make check`：backend 276 passed / 3 skipped；frontend 22 files / 122 tests passed，
  format、lint、typecheck、build 与 generated contract check 全部通过。
- operator docs：更新 authority `docs/operations/deployment.md`，记录单 API 进程内 publication
  loop、两项默认配置、restart recovery 和单实例边界；不暗示独立 Worker、生产就绪或整个
  Issue #46 完成。`deploy/README.md` 已把运行原理和生产边界指向该 authority，无需重复。
- 无临时 scaffold；本仓库未采用本 slice 对应的 changelog，因此不新增并行发布记录。

## 消费者
- FastAPI Shared Resource routes/presenters/schemas
- application access guard 与 repository implementation
- frontend API client、`PublishVersionModal`、Shared Resource detail refresh
- existing Shared Resource integration helpers/tests that currently assume synchronous Version creation
- generated OpenAPI and TypeScript schema

## 禁区
- 不碰 Environment、Run Configuration、Preflight 或旧 M1 Run worker
- 不建通用 Asset / validator / job / plugin / queue framework，不加依赖
- 不访问 live 107，不 push/commit，不操作其他 worktree
- 不保留兼容 alias、旧同步 endpoint 语义或 deprecated dual path
- 不加依赖
