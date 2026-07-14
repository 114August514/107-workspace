# 架构与模块变化

本文按代码层说明相对旧 RunBox 新增的活动后端。整体采用模块化单体：部署单元
保持简单，但领域、应用、基础设施和 HTTP 边界可以独立理解、测试和协作。

## 1. 分层约束

```text
workspace107.api
        |
        v
workspace107.application
        |
        v
workspace107.domain  <--- defines ports
        ^
        |
workspace107.infrastructure  --- implements ports
```

约束如下：

1. `domain` 只使用 Python 标准库，不导入 FastAPI、SQLAlchemy、Slurm 或 SSH。
2. `application` 只依赖领域对象和端口，不依赖 API 或具体基础设施。
3. `infrastructure` 实现领域端口，封装数据库、文件系统、子进程和远程协议。
4. `api` 负责身份头、schema、路由和错误映射，不直接操作数据库模型。
5. [main.py](../../../backend/src/workspace107/main.py) 是唯一组合根，负责选择和连接 adapter。

审计扫描未发现领域层反向依赖，也未发现应用层导入 API 或基础设施。

## 2. 仓库级结构

```text
107-workspace/
|-- archive/runbox-v0/       # 旧实现源码快照
|-- backend/                 # 当前活动后端
|-- docs/                    # 设计、计划和审阅材料
|-- scripts/                 # 仓库级验收脚本
|-- frontend/                # 延期标记
|-- docker/                  # 延期标记
`-- deploy/                  # 延期标记
```

根目录不再承担 Python 包职责。活动后端独立拥有依赖、锁文件、迁移、源码和测试，
从而避免归档代码或同级参考项目隐式进入运行环境。

## 3. Domain

入口：[../../../backend/src/workspace107/domain/](../../../backend/src/workspace107/domain/)

领域层新增以下业务对象：

- `User`：开发阶段身份记录。
- `Workspace` 与 `WorkspaceMember`：课程、团队、实验等协作空间及角色关系。
- `Project` 与 `ProjectSync`：项目元数据和传输历史。
- `Dataset` 与 `DatasetVersion`：逻辑数据集和不可变版本。
- `RunTemplate`：入口、环境、资源和输出声明。
- `Run`、`RunDataset` 与 `RunEvent`：不可变提交快照、挂载和状态历史。
- `Artifact`：日志、结果和声明输出的元数据。

领域规则包括：

- owner、manager、member、viewer 的权限判断；
- 最终 owner 不得被删除或降级；
- 归档资源不能进入新运行；
- 运行只能按状态机进行合法、单向转换；
- 挂载点、入口和输出必须是安全的 POSIX 相对路径；
- 领域错误使用稳定类别，而不是泄漏底层异常。

领域端口包括 Cluster、ProjectTransfer、Storage 和 Repository/UoW。应用层面向这些
端口编程，因此 Mock、Slurm、Local 和 SSH 实现可以替换而不改变业务用例。

## 4. Application

入口：[../../../backend/src/workspace107/application/](../../../backend/src/workspace107/application/)

| 模块 | 职责 |
| --- | --- |
| `access.py` | 统一工作区访问和角色校验 |
| `users.py` | 用户创建与读取 |
| `workspaces.py` | 工作区、父子关系、成员和归档 |
| `projects.py` | 项目 CRUD 与归档 |
| `datasets.py` | 数据集、不可变版本和对象存储协调 |
| `templates.py` | 运行模板 CRUD 与规格校验 |
| `inference.py` | 入口、依赖环境和资源推断 |
| `preflight.py` | 项目、模板、数据集、路径和资源预检 |
| `transfers.py` | 项目扫描、push、pull 和同步记录 |
| `runs.py` | 提交、状态、取消、日志、事件和产物编排 |

运行提交是最关键的应用流：

```text
读取并校验资源
    -> 生成不可变 submission snapshot
    -> 提交数据库事务
    -> 在事务外调用 ClusterPort.submit
    -> 用 CAS 记录 external_job_id 和 queued 状态
    -> reconciler 持续对账直至终态
    -> 收集日志与产物到 StoragePort
```

外部 adapter 调用不占用数据库事务；并发写入通过 compare-and-set 约束。这里是
协作和后续扩展的核心边界，也是需要重点审阅失败窗口的地方。

## 5. Infrastructure

入口：
[../../../backend/src/workspace107/infrastructure/](../../../backend/src/workspace107/infrastructure/)

### 5.1 数据库

- SQLAlchemy async engine 和 session factory；SQLite 默认启用外键和 WAL。
- 初始 Alembic 迁移创建 12 张业务表。
- Repository 覆盖用户、工作区、成员、项目、数据集、模板、运行、事件和产物。
- Unit of Work 统一 commit、rollback 和异常退出语义。

### 5.2 本地存储

- 数据集与运行产物使用 SHA-256 内容寻址。
- 写入采用临时文件和原子替换，失败时清理中间文件。
- 下载通过存储 key 和数据库授权关系访问，不接受任意绝对路径。

### 5.3 项目扫描与传输

- scanner 支持 `.hpcignore`、目录剪枝、Unicode 路径和符号链接检查。
- manifest 用路径、大小、mtime 和摘要支持增量比较。
- LocalProjectTransfer 适用于共享文件系统或单机开发。
- SshProjectTransfer 使用 PAX tar 管道，不把请求值拼成 shell 片段。
- 所有源、目标和文件路径都必须位于服务端配置的允许根目录内。

### 5.4 集群 adapter

- Durable Mock 将外部状态、日志和结果持久化，应用重启后可以继续对账。
- Slurm renderer 使用严格模板、资源校验和安全路径。
- parser 将 `squeue`、`sacct` 和 `sbatch --parsable` 输出归一为领域状态。
- LocalCommandRunner 使用参数数组执行本地命令。
- SshCommandRunner 只接受服务端配置的可信 host，并引用完整远程参数列表。

### 5.5 Reconciler

后台 reconciler 轮询非终态运行，追加事件、收集终态日志和产物，并隔离单个作业的
adapter 异常。它依赖 CAS 和幂等检查，避免重复终态更新或重复产物收集。

## 6. API

入口：[../../../backend/src/workspace107/api/](../../../backend/src/workspace107/api/)

活动后端定义 42 个 HTTP 路由操作，包括：

- 健康检查和用户；
- 工作区、成员和归档；
- 项目 CRUD、scan、push 和 pull；
- 数据集、版本上传和下载；
- 运行模板；
- 运行 preflight、提交、列表、详情和取消；
- 运行事件、分段日志、可重连 SSE；
- 产物列表和下载。

API 使用独立 Pydantic schema，不暴露 SQLAlchemy row。领域错误统一映射为
`application/problem+json`，外部命令和路径错误使用经过清理的公共描述。

当前身份边界是 `X-User-Id`：它适合后端阶段的开发和验收，但默认信任调用方，
不能被当作生产认证机制。

## 7. 运行时组合

[main.py](../../../backend/src/workspace107/main.py) 根据配置完成以下选择：

- 默认 `mock` cluster adapter；
- 可选 `slurm` cluster adapter；
- Slurm 可使用 `local` 或 `ssh` command transport；
- SSH cluster transport 同时选择 SSH project transfer，保证同步与运行在同一侧；
- 启动和关闭数据库 engine、reconciler task 及相关资源。

这种组合方式保持应用服务不感知运行环境，也让测试可以注入 fake adapter、时钟、
存储和 UoW。

## 8. 架构审阅重点

1. 确认 API、application、domain、infrastructure 没有越层访问。
2. 对照领域约束检查 SQLAlchemy schema 和 Repository 查询范围。
3. 检查外部调用前后事务边界及补偿策略。
4. 检查所有文件路径和远程参数是否在启动进程前完成验证。
5. 检查 reconciler、取消和产物收集在重复调用下是否幂等。
6. 检查 Mock 与 Slurm 是否真正通过同一 ClusterPort 合同表现一致。
