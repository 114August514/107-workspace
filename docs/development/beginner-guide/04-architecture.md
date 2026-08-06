# 第四章：仓库结构与系统架构

架构的作用不是增加术语，而是告诉开发者“代码应放在哪里、谁可以依赖谁”。先掌握这些边界，
再阅读具体实现会轻松很多。

## 4.1 顶层目录

```text
107-workspace/
├── backend/       FastAPI 后端、迁移和后端测试
├── frontend/      React 控制台和前端测试
├── contracts/     OpenAPI 等跨组件机器契约
├── deploy/        Docker Compose 等可执行部署编排
├── scripts/       跨平台任务入口
├── docs/          活动文档、决策、参考和文档归档
└── archive/       旧实现快照，只用于追溯
```

服务自己的构建文件跟随服务维护，例如 `backend/Dockerfile` 和 `frontend/Dockerfile`；多个服务
如何组合则放在 `deploy/`。机器生成的接口契约放在 `contracts/`，不和人工说明混在一起。

## 4.2 系统运行时关系

开发环境中主要有五部分：

```text
浏览器
  |
React / Vite
  |
FastAPI
  +----> SQLite 或 PostgreSQL
  +----> 本地或共享 Storage
  +----> Mock Scheduler 或 slurmrestd
```

前端只通过 HTTP API 使用后端。后端保存长期业务数据，Storage 保存项目内容、运行目录、日志和
产物，Scheduler 负责执行状态。它们的数据不能互相替代：数据库中显示“成功”，并不意味着
产物文件一定存在；文件存在，也不能跳过权限和业务状态检查直接暴露给用户。

## 4.3 模块化单体

当前后端是模块化单体：大多数业务模块运行在同一个 FastAPI 进程中，但内部仍按职责分层。
这样部署和本地调试较简单，同时能保持业务规则独立。目标设计中还需要独立 Worker，但在它
真正实现前，不应假装当前已经存在对应进程边界。

“单体”不表示路由、SQL 和业务判断可以写在一个函数里。项目采用下面的单向依赖：

```text
api  →  application  →  domain ports  ←  infrastructure
```

箭头表示源码依赖方向，不表示一次请求只能按箭头执行。Application 会通过端口调用
Infrastructure 的实现，但它 import 的是 Domain 中的抽象协议，而不是具体数据库类。

## 4.4 四层分别负责什么

### API

路径：`backend/src/workspace107/api/`

负责 HTTP 路由、请求/响应 Schema、身份依赖、中间件和错误转换。它知道状态码和请求头，但
不应该包含核心业务判断，也不能绕过 Application 直接使用 Repository。

### Application

路径：`backend/src/workspace107/application/`

负责“完成一项用户操作”所需的编排，例如创建项目、提交 Run、同步状态。这里是访问检查、
事务边界以及多个端口协作的主要位置。

### Domain

路径：`backend/src/workspace107/domain/`

负责模型、枚举、不变量、值对象和端口协议。它不 import 数据库、HTTP、文件、时钟或随机数
实现，因此可以用毫秒级纯单元测试密集覆盖。

### Infrastructure

路径：`backend/src/workspace107/infrastructure/`

负责 SQLAlchemy、文件系统、Mock/Slurm 调度、真实时钟等外部细节。基础设施可以依赖 Domain
协议，Domain 不能反过来依赖它。

## 4.5 Port 和 Adapter

Port 可以理解为“业务需要什么能力”的接口，Adapter 是“某种环境怎样提供这个能力”的
实现。例如 Domain 只要求 Scheduler 能提交、查询和取消任务：

```text
Scheduler Port
├── Mock Adapter：在本机启动子进程
└── Slurm Adapter：调用 Slurm REST API
```

类似端口还有 Storage、Secret Vault、Clock 和 Repository。增加新的外部能力时，通常先定义
端口，再在 Infrastructure 中实现；增加新的用户操作时，通常增加或扩展 Application Service。

不要为了少写几个参数，把具体数据库 Session 或 Scheduler 塞进所有对象。显式依赖更容易
测试，也让调用者知道一项用例实际需要什么。

## 4.6 依赖注入和装配入口

项目目前只在两个组合入口构造具体实现：

- `main.py` 组装进程级对象，如数据库引擎、Storage、Scheduler 和 Clock；
- `api/deps.py` 组装请求级对象，如 Repository、Secret Vault 和用例服务。

路由通过 `Services` 容器取得 Application Service。容器不暴露 Repository 和端口，这是防止
路由绕过权限、事务和领域规则的一道工程边界。

## 4.7 新代码放在哪里

收到需求时可以按下面顺序判断：

| 变化 | 常见位置 |
| --- | --- |
| 新业务规则或状态判断 | `domain/` |
| 一项操作需要协调多个对象 | `application/` |
| 新 HTTP 路径或请求字段 | `api/` |
| 新数据库查询或外部系统调用 | `infrastructure/` |
| 新页面或用户交互 | `frontend/src/pages` 或 `components` |
| 前后端共享字段变化 | 后端 DTO，然后重新生成 `contracts/` |

一个垂直功能往往会同时改几层。这并不违反分层；关键是每层只保存属于自己的判断，依赖方向
不反转。

## 4.8 用源码验证架构理解

第一次读仓库可以选择 Run 主链路，按以下文件顺序查看：

1. `frontend/src/components/run/SubmitRunModal.tsx`
2. `frontend/src/api/client.ts`
3. `backend/src/workspace107/api/routes/runs.py`
4. `backend/src/workspace107/application/run_service.py`
5. `backend/src/workspace107/domain/run_snapshot.py`
6. `backend/src/workspace107/domain/ports/scheduler.py`
7. `backend/src/workspace107/infrastructure/scheduler/mock.py`
8. `backend/src/workspace107/application/run_lifecycle.py`

不要试图第一次就读完所有模型。先找入口和出口，再只展开当前函数调用到的对象。

