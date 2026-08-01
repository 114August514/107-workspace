# ADR-0005 容器化部署形态

状态：已接受 · 阶段：M1 · 相关：GR-012、GR-015

## 背景

M1 只能在开发机上跑：SQLite、`uvicorn --reload`、Vite dev server、
前端靠 dev proxy 转发 `/api`。要做演示、要让别人试用、要往真实环境推进，
需要一个能一条命令起来、又不是玩具的部署形态。

需要先分清一件事：**这里的容器化是给 107 Workspace 应用自己用的**，
和用户作业怎么跑没有关系。用户作业走 Slurm + Apptainer 在计算节点上执行
（见 [ADR-0004](0004-runtime-backend.md)），不在这些容器里。

## 决策

### 1. 三个容器：db / api / web

```text
浏览器
   │  :8107
   ▼
 web (nginx)
   ├── /            前端静态资源
   └── /api  ──────► api (uvicorn)
                        │
                        ▼
                   db (PostgreSQL)
```

前端和后端**同源**，`/api` 由 nginx 反代。这样生产环境完全不需要 CORS——
`main.py` 里那段 CORS 中间件只在 `env=local` 时挂载，容器里根本不会生效。

### 2. 后端镜像多阶段构建，运行阶段不带构建工具

```text
构建阶段    uv 镜像 → uv sync --frozen --no-dev --extra postgres
运行阶段    python:3.12-slim → 只复制 .venv 和 src
```

依赖层和源码层分开复制，改代码不会让依赖层缓存失效。

两个镜像都用**非 root 用户**运行。前端用 `nginx-unprivileged`，
监听 8080 而不是 80，省掉 `CAP_NET_BIND_SERVICE`。

健康检查不额外装 curl：后端用 `python -c urllib.request...` 打自己的
`/api/v1/health`，前端用 alpine 自带的 `wget --spider`。少装一个包就少一份攻击面。

### 3. 启动时执行迁移和平台目录种子

api 容器的入口脚本先做两件事再拉起 uvicorn：

```text
alembic upgrade head              把数据库结构升到最新
python -m workspace107.tools.seed 载入平台运行环境与算力方案（幂等）
```

种子**只载入平台目录，不载入演示项目**。理由：运行环境和算力方案是应用能工作的
前提（没有算力方案就建不了运行方案），属于平台数据；而演示 Project 是给人看的，
应该由使用者显式要求。演示数据通过 `--demo` 参数单独载入。

平台目录本来应该由平台管理后台维护（设计稿 §2.13 E），那部分还没做，
启动时种子是这期间诚实的过渡方案，不是长期形态。

**这个方案的前提是单实例。** 多副本同时启动会有迁移竞争，
到那一步要把迁移拆成独立的一次性任务（K8s 里就是 Job 或 initContainer）。
现阶段单机 compose 没必要提前上这套复杂度，但要写在这儿，别到时候忘了。

### 4. 配置全部从环境变量注入，镜像里不含任何凭据

```text
仓库里    .env.example    只有变量名和说明
部署机    .env            真实值，被 .gitignore 和 .dockerignore 同时排除
镜像里    什么都没有
```

`WORKSPACE107_SLURM_JWT` 等价于密码。它只能通过环境变量进入容器，
不写进镜像、不写进 compose 文件、不进仓库（GR-012 的部署侧对应）。

`.dockerignore` 要显式排除 `.env`、`backend/var/`、`.venv/`、`node_modules/`——
不然一个 `COPY . .` 就把本地数据库和依赖目录一起烤进镜像了。

### 5. 存储用 volume，但接真实集群时必须换成共享文件系统

这是整个部署里**最容易踩的坑**，单独说清楚。

用 mock 调度器时，作业就在 api 容器里以子进程执行，Run 目录只有它自己读写，
docker volume 完全够用。

但换成 Slurm 之后：

```text
api 容器          准备 Run 工作目录、写入代码和输入
   │
   ▼
Slurm 计算节点     执行作业，读工作目录，写 stdout / stderr 和产物
   │
   ▼
api 容器          回来读日志、收集 Artifact
```

两边必须看到**同一份文件系统**。docker volume 只在本机可见，计算节点看不到，
作业会立刻失败。所以生产部署时 `WORKSPACE107_STORAGE_ROOT` 必须指向集群的
共享存储挂载点，并且 api 容器要以 bind mount 的方式挂进去。

这一条写进部署文档的显眼位置。

### 6. mock 调度器只用于演示

compose 默认 `WORKSPACE107_SCHEDULER=mock`，一条命令就能看到完整闭环，
不需要集群。但 mock 是在 api 容器里跑用户代码——
**任何有权提交 Run 的人都能在容器里执行任意命令**。

所以：演示和内部试用可以，对外提供服务必须切到 `slurm`。
部署文档里把这句话写成警告，不是脚注。

### 7. 镜像发布由 tag 驱动，PR 只验证能构建

```text
每个 PR        docker-build 作业构建两个镜像，不推送
打 v* tag      release 工作流构建并推送到 GHCR
```

PR 上构建的意义是：Dockerfile 坏了当场就知道，而不是等到发版。
不推送是因为 PR 分支的镜像没人需要，推了只是占空间。

## 放弃的方案

**单容器：把前端静态文件打进后端镜像，用 FastAPI 的 StaticFiles 提供。**
少一个容器，但改一行前端就得重建后端镜像；而且静态资源的缓存头、gzip、
SPA fallback 这些事 nginx 做得更好，用 Python 重新实现一遍没有意义。

**生产也用 SQLite。** 并发写会锁，而且没法从另一个容器访问。
本地开发用它很合适，生产不行。

**把迁移做成独立的 compose service，用 `depends_on` 串起来。**
compose 的 `depends_on: service_completed_successfully` 能表达，
但对单实例部署来说，入口脚本里两行命令更直观，也少一个容器。
多副本时再拆。

**在 compose 文件里写死数据库密码。** 那等于提交到仓库。全部走 `.env`。

## 影响

- `tools/seed.py` 需要区分「平台目录」和「演示数据」，加一个 `--demo` 参数
- `Settings.ensure_local_directories()` 在容器里也会跑，volume 挂载点的属主
  必须是容器里的非 root 用户，Dockerfile 里要 `chown`
- CI 增加 `docker-build` 作业，GitGuideline §8 里本来就把它列为后续要加的检查
- 部署文档需要明确写出「mock 不能对外」和「Slurm 必须共享存储」两条约束
- 之后要上 K8s 的话，迁移要从入口脚本里拆出来（见第 3 条）
