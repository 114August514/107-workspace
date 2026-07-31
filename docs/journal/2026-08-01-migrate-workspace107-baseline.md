# 迁移 workspace107 已实现基线

- 状态：已完成
- 认领：August / Codex
- 上下文：repository-wide migration
- 开始：2026-08-01
- 结束：2026-08-01 02:23 +0800

## 意图

把 `workspace107@293c8d8` 的已实现部分迁入本仓库，以根目录
`DESIGN-final.md` 和 `GitGuideline.md` 为准完成适配；同时保留双方可审查历史，避免
协作者面对两套活动实现。

## 范围

- 归档完整来源快照，固定迁移前目标提交。
- 迁移 backend、frontend、API Contract、容器和协作配置。
- 放弃未完成的 `transfer -> execution_data` WIP。
- 建立跨平台 Python 任务入口、薄 Makefile 和 Windows/POSIX 引导脚本。
- 将前端工具链固定为 Node.js 24 LTS、pnpm 11 stable 和唯一 pnpm 锁文件。
- 清理活动代码里的旧 GR/Milestone 引用，更新协作文档。
- 验证检查、构建、数据库升级/回退/再升级和本地 Mock 闭环。

## 非目标

- 不声称完成 `DESIGN-final.md` 的 M1 Executable Skeleton。
- 不在本次实现真实 Git、Shared FS、独立 Worker、Apptainer、USTC 认证或生产运维。
- 不把来源仓库的旧产品、领域、Milestone、ADR 和 Git 文档提升为活动规范。
- 不自动删除或转换已有 `backend/var/` 开发数据。

## 已形成的历史锚点

- 迁移前目标：`archive/pre-workspace107-migration-2026-08-01` -> `7085435`
- 来源：`workspace107@293c8d8b0ff6a43be4b31d62447fb332779862d5`
- 来源归档提交：`3896b0a`
- 活动设计基线提交：`ddc51e0`
- 后端迁移提交：`077ab45`
- 前端迁移提交：`bbe269f`

## 回退

已提交迁移用 `git revert` 逐个反向应用；需要查看替换前完整状态时使用归档 tag。
未提交适配只按文件审查后撤销，不使用破坏工作区的全局 reset。

## 验收结果

- `make check`：通过。工作流单测 9 项、后端 269 项、前端 61 项通过；Ruff、
  Prettier、ESLint、TypeScript、前后端 build 和 API Contract 检查均通过。
- `make contract`：通过；已生成 `docs/api/openapi.json` 和
  `frontend/src/api/schema.d.ts`，随后契约差异检查通过。
- pnpm：Node `v24.18.0`、pnpm `11.18.0`；冻结安装通过，安装脚本只允许
  `esbuild`；npm 锁文件已由 `pnpm-lock.yaml` 替代。
- 临时 SQLite 数据库：`upgrade head -> downgrade -1 -> upgrade head` 通过。
- `make smoke` 与 `make demo`：通过；Project -> Version -> Run Snapshot -> Log ->
  Artifact 的隔离 Mock HTTP 闭环成功，产物内容与日志经过断言。
- `make doctor`：通过；仅提示当前 clone 尚未启用可选 Git hooks。
- `docker compose config`：通过；后端和 Node 24/pnpm 11 前端镜像均实际构建成功。
- 独立 Compose project：db/api/web 健康，健康接口、seed 后的 Compute Plan 目录和
  前端 HTML 均可访问；验证容器、网络和卷随后已删除。
- 活动源码、测试、生成契约和维护文档不再引用来源仓库缺失的 ADR、旧 GR 或旧阶段
  说明。Alembic 历史和归档仍保留其创建时用语。
- 来源归档对象级校验通过：排除新增的 `ARCHIVE.md` 后，来源提交的 232 个文件在
  路径、mode 和 blob SHA 上全部一致，归档提交后未再变化。

## 剩余风险与未验证项

- 尚未在真实 Windows runner 上执行；本地只覆盖了平台分支单测，Windows CI 已使用
  无 Make 入口约束完整检查和 smoke。
- 真实 Git、Shared FS、独立 Worker、Apptainer、USTC 认证和 Slurm 环境均未验收，
  因此本次迁移不构成现行 M1 完成声明。
- 受限沙箱内曾出现 aiosqlite 连接等待；同一迁移链在沙箱外通过，完整后端测试也
  通过。后续 CI 若复现，需要单独调查异步 SQLite fixture/worker 生命周期。
- 前端生产构建仍有约 1.3 MB 主 chunk 的 Vite 警告；不阻塞本次基线迁移，但应在
  后续性能工作中拆包。
- 远程默认分支目前仍是 `master`，而 `GitGuideline.md` 规定长期分支为 `main`；CI
  过渡期同时监听两者，分支改名应由维护者单独执行。

## 完成时仓外副作用

- 本地 annotated tag 保留；未 push、未部署、未写入远程数据库。
- 本地生成了 `workspace107/api:local` 与 `workspace107/web:local` 两个验证镜像。
- Compose 验证使用独立 project 和端口；其容器、网络、数据库卷和存储卷已删除。
