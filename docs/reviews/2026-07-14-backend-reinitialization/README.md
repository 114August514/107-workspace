# 后端重初始化审阅总览

本文档集记录 `107-workspace` 后端重初始化的历史审阅快照。比较范围是
`origin/master` 到 `5d69a47` 的 17 个提交；快照采集于 2026-07-14，当时这些提交
尚未推送，工作区没有 staged、unstaged 或 untracked 改动。

> 本审阅包在快照之后单独提交，不属于下述 17 个实现提交，也不计入快照中的
> 文件和行数。审阅时应将“被审阅的代码改动”和“后续说明文档”分开看待。

## 1. 总体结论

这批改动不是对旧 RunBox 的局部修补，而是一次完整的后端优先重初始化：

- 原 RunBox 作为源码快照归档到 `archive/runbox-v0/`，不再参与活动代码运行。
- 新增独立的 Python 3.12、FastAPI、SQLAlchemy 和 Alembic 后端工程。
- 后端采用模块化单体，依赖方向固定为
  `api -> application -> domain ports <- infrastructure`。
- 已实现用户、工作区与成员、项目、版本化数据集、运行模板、预检、运行提交、
  日志、取消、事件和产物下载等后端流程。
- 默认使用可持久化的 Mock 调度器；可显式切换 Slurm local 或 Slurm SSH。
- RunBox、`submit107` 和 `hpc-helper` 的可用行为被重新实现到本项目内部，
  活动后端不依赖或导入这些参考项目。
- 前端、容器化和部署仍然延期，本轮只完成并验收后端。

因此，审阅不宜从 160 个文件的平铺 diff 开始。推荐先确认架构边界，再沿领域、
持久化、运行工作流和远程执行边界逐层审阅。

## 2. Git 快照

| 项目 | 值 |
| --- | --- |
| 当前分支 | `master` |
| 比较基线 | `origin/master` / `72d975c6dd4324fc33b773de91bddeb190ce9e6f` |
| 被审阅 HEAD | `5d69a4746c86df37e214c13bfc8fd76fdcdccae0` |
| 分叉状态 | ahead 17，behind 0 |
| 快照时工作区 | 干净 |
| 最终差异 | 160 个文件，`+20,660 / -183` |
| `backend/` 差异 | 132 个文件 |
| 测试相关文件 | 50 个，其中 42 个 `test_*.py` 测试模块 |
| HTTP 路由操作 | 42 个路由装饰器 |

比较命令：

```bash
git status --short --branch
git log --reverse --oneline origin/master..5d69a47
git diff --shortstat origin/master..5d69a47
git diff --stat origin/master..5d69a47
```

## 3. 架构总图

```text
HTTP / FastAPI
      |
      v
workspace107.api
      |
      v
workspace107.application
      |
      v
workspace107.domain  <--- ports
      ^
      |
workspace107.infrastructure
  |-- SQLAlchemy / Alembic
  |-- LocalStorage
  |-- Local / SSH project transfer
  |-- Durable Mock scheduler
  |-- Slurm local / SSH adapter
  `-- background reconciler
```

核心判断是：领域层定义业务语言和端口，应用层编排用例，基础设施实现外部能力，
API 只负责 HTTP 映射。外部参考项目的行为进入基础设施或应用策略，而不是进入
运行时依赖。

## 4. 文档导航

| 文档 | 回答的问题 |
| --- | --- |
| [01-change-phases.md](01-change-phases.md) | 17 个提交如何组成八个连续实施阶段？ |
| [02-architecture-and-modules.md](02-architecture-and-modules.md) | 各代码层新增了什么，关键调用流如何工作？ |
| [03-reference-absorption.md](03-reference-absorption.md) | RunBox、`submit107`、`hpc-helper` 吸收了什么，又排除了什么？ |
| [04-testing-and-acceptance.md](04-testing-and-acceptance.md) | 哪些质量门和 12 项验收标准已有直接证据？ |
| [05-risks-and-deferred.md](05-risks-and-deferred.md) | 审阅时应重点检查哪些风险，哪些范围仍然延期？ |
| [06-commit-index.md](06-commit-index.md) | 每个提交的主题、规模和审阅重点是什么？ |

## 5. 推荐审阅顺序

1. 阅读 [后端设计规格](../../superpowers/specs/2026-07-13-workspace107-backend-design.md)，
   确认目标、非目标、分层规则和验收标准。
2. 阅读 [01-change-phases.md](01-change-phases.md)，建立提交之间的依赖顺序。
3. 审阅 `domain` 的模型、权限、状态机和端口，再审阅数据库模型与迁移。
4. 审阅资源类 API：工作区、成员、项目、数据集和模板。
5. 审阅运行提交的事务边界、不可变快照、CAS 更新和 reconciler 幂等性。
6. 审阅项目传输的允许根目录、符号链接、增量语义和 tar 管道。
7. 最后集中审阅 Slurm/SSH 命令构造、状态映射、取消和产物收集。
8. 用 [04-testing-and-acceptance.md](04-testing-and-acceptance.md) 对照测试证据，
   再用 [05-risks-and-deferred.md](05-risks-and-deferred.md) 做收尾判断。

## 6. 审阅边界

本审阅集包含：

- `origin/master..5d69a47` 的全部版本化差异；
- RunBox 归档和根目录重置；
- 后端源码、迁移、测试、脚本与开发文档；
- 参考项目行为的吸收方式和独立性证据；
- 当前已知风险、非目标与延期范围。

本审阅集不把以下内容当作已实现能力：

- 真实 Slurm 集群和凭据环境下的现场验收；
- 生产级认证、授权网关或完整多租户安全边界；
- 前端、Docker 镜像、部署编排或 SCOW 集成；
- `hpc-helper` 的 batch grouping；当前活动代码没有对应模型或 API；
- 旧 RunBox 的独立可运行性；归档仅保证源码可追溯。

## 7. 快速入口

- 项目说明：[../../../README.md](../../../README.md)
- 后端开发指南：[../../../backend/README.md](../../../backend/README.md)
- 后端设计规格：
  [../../superpowers/specs/2026-07-13-workspace107-backend-design.md](../../superpowers/specs/2026-07-13-workspace107-backend-design.md)
- 实施计划：
  [../../superpowers/plans/2026-07-13-workspace107-backend.md](../../superpowers/plans/2026-07-13-workspace107-backend.md)
- RunBox 归档说明：[../../../archive/runbox-v0/ARCHIVE.md](../../../archive/runbox-v0/ARCHIVE.md)
- 平台资料归档：[../../archive/2026-07-14-platform-materials/README.md](../../archive/2026-07-14-platform-materials/README.md)
- HTTP 验收脚本：[../../../scripts/smoke-backend.sh](../../../scripts/smoke-backend.sh)
