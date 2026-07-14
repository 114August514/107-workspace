# 后端重初始化实施阶段

本文按依赖顺序将 17 个被审阅提交归纳为八个阶段。阶段划分用于理解演进关系，
不是新的 Git 历史；逐提交信息见 [06-commit-index.md](06-commit-index.md)。

## 1. 总体演进

```text
规格与计划
    -> 归档旧实现并建立独立工程
    -> 定义领域模型和端口
    -> 建立数据库与 UoW
    -> 实现协作资源 API
    -> 实现模板、预检和项目传输
    -> 实现 Mock 运行工作流
    -> 实现 Slurm / SSH
    -> 完成文档与验收
```

| 阶段 | 提交 | 结果 |
| --- | --- | --- |
| 1. 架构规格 | `d9a3fff`, `17bcf6c` | 明确目标、边界、分层规则、实施任务和验收标准 |
| 2. 仓库重置 | `28fc895`, `409782b` | 归档 RunBox，建立独立后端和延期目录 |
| 3. 领域与持久化基础 | `bdd5186`, `e5056e7`, `a7828e8`, `dfe72ba` | 建立领域语言、端口、12 表 schema、Repository 和 UoW |
| 4. 协作资源 API | `9c98742`, `f416583` | 实现用户、工作区、成员、项目和版本化数据集 |
| 5. 模板与传输 | `bc945ea`, `dda4061` | 实现运行模板、推断、预检、扫描和增量传输 |
| 6. Mock 运行工作流 | `cc87aef`, `a321a0b`, `9be962a` | 实现持久 Mock、运行编排、reconciler、SSE 和产物 |
| 7. Slurm 与 SSH | `cf9fa4c` | 实现分层 Slurm adapter 和安全 SSH/tar 传输 |
| 8. 验收收尾 | `5d69a47` | 补全文档、HTTP smoke、边界覆盖率和一处 SSH 错误映射 |

## 2. 阶段一：架构规格

提交：`d9a3fff`, `17bcf6c`

主要变化：

- 将[初始后端搭建指南](../../references/engineering/initial-backend-bootstrap-guide.md)、
  [产品愿景](../../references/product/107-workspace-product-vision.md)、RunBox、
  `submit107` 和本地 `hpc-helper` 作为设计证据。
- 确定模块化单体，而不是拆分微服务。
- 定义四层依赖、领域模型、端口、HTTP API、安全规则和 12 项验收标准。
- 将实施过程拆成 15 个可独立提交的任务。

审阅重点：规格中的目标和非目标是否符合当前阶段；尤其确认生产认证、现场集群
验收、前端和容器化确实不在本轮范围内。

## 3. 阶段二：仓库重置

提交：`28fc895`, `409782b`

主要变化：

- 旧 `runbox/`、`DESIGN.md` 和原 `pyproject.toml` 移入 `archive/runbox-v0/`。
- 删除 `runbox.egg-info`、`__pycache__` 等生成物。
- 新建 `backend/`，拥有自己的 `pyproject.toml`、`uv.lock` 和 Python 版本约束。
- 建立 FastAPI 组合根、配置、健康检查及基础质量门。
- `frontend/`、`docker/`、`deploy/` 只保留延期标记。

审阅重点：活动后端是否与归档完全隔离；根目录导航是否明确；独立安装是否只依赖
`backend/pyproject.toml` 和 `backend/uv.lock`。

## 4. 阶段三：领域与持久化基础

提交：`bdd5186`, `e5056e7`, `a7828e8`, `dfe72ba`

主要变化：

- 定义用户、工作区、成员、项目、数据集版本、模板、运行、事件和产物等领域模型。
- 定义成员权限、最终 owner 约束、相对路径值对象和运行状态机。
- 用 Protocol 定义 Cluster、Storage、Transfer 和 Repository 端口。
- 建立 12 张 SQLAlchemy 表和 Alembic 初始迁移。
- 实现 Repository 与 Unit of Work，统一事务边界和 compare-and-set 更新。

审阅重点：领域模型与数据库模型是否保持语义一致；唯一约束、外键、不可变版本和
状态转换是否同时被数据库、应用服务和测试覆盖。

## 5. 阶段四：协作资源 API

提交：`9c98742`, `f416583`

主要变化：

- 实现开发身份、工作区 CRUD、父子工作区规则和成员角色管理。
- 实现项目 CRUD、归档、扫描和传输入口。
- 实现数据集及不可变版本上传、列表和下载。
- 引入内容寻址本地存储，按 SHA-256 管理数据和产物。
- API 统一使用 `/api/v1`、Pydantic schema 和 Problem Details 错误响应。

审阅重点：角色权限、归档资源行为、slug 冲突、父工作区约束和下载访问控制。

## 6. 阶段五：模板与传输

提交：`bc945ea`, `dda4061`

主要变化：

- 实现运行模板、环境规格、资源规格和输出声明。
- 从项目文件推断入口、依赖环境和资源，形成可解释的 preflight 检查。
- 实现 `.hpcignore`、目录剪枝、manifest 和增量扫描。
- 实现允许根目录约束下的 LocalProjectTransfer。
- 对路径穿越、根目录逃逸和符号链接逃逸建立拒绝规则。

审阅重点：推断只提供建议还是形成强制规则；路径规范化是否在启动外部进程之前
完成；增量传输对新增、跳过和移除文件的语义是否清楚。

## 7. 阶段六：Mock 运行工作流

提交：`cc87aef`, `a321a0b`, `9be962a`

主要变化：

- Mock 调度器将外部作业状态、日志和结果原子化持久到 JSON 与文件系统。
- RunService 固化不可变提交快照，在数据库事务外调用集群 adapter。
- 使用 CAS 更新处理并发状态变更，后台 reconciler 负责轮询、事件和产物收集。
- 实现运行预检、提交、查询、取消、事件、日志、可重连 SSE 和产物下载 API。
- 验证 Mock 外部状态可以跨应用重建继续运行。

审阅重点：事务提交与外部调用的失败窗口、取消竞态、终态幂等、日志 offset、
reconciler 重试以及产物只收集一次的保证。

## 8. 阶段七：Slurm 与 SSH

提交：`cf9fa4c`

主要变化：

- 将 sbatch 渲染、Slurm 输出解析、命令执行和 adapter 分成独立模块。
- 支持 `sinfo`、`sbatch`、`squeue`、`sacct`、`scancel` 的结构化调用和状态映射。
- 支持登录节点本地执行和受信任 SSH alias 两种 transport。
- 实现 PAX tar 流式项目传输、双进程清理和 SSH 命令参数引用。
- 用 fake runner、contract tests 和安全测试覆盖，不需要真实集群凭据。

审阅重点：这是最高风险阶段。应重点检查远程命令引用、作业 ID 校验、Slurm
状态归一化、取消语义、metadata 路径、tar 选项终止和管道失败清理。

## 9. 阶段八：验收收尾

提交：`5d69a47`

主要变化：

- 扩展根 README 和后端开发指南。
- 新增真实 Uvicorn 的 HTTP smoke 脚本及完整 Mock 工作流。
- 增加 API、Mock、Slurm、SSH、运行时和错误边界测试，将分支覆盖率提升到门槛以上。
- 修复 SSH 项目传输中缺失本地文件泄漏 `FileNotFoundError` 的问题，统一映射为
  `ResourceNotFound`。

审阅重点：该提交虽以 `docs:` 命名，但包含生产代码变化；审阅时不能只检查文档。
同时确认 smoke 验证的是 TCP 上的真实服务，而不是仅使用 ASGI 内存 transport。
