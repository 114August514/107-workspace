# 部署

这里说明如何把 **107 Workspace 应用自身**部署起来。

用户作业不在这些容器里跑——它们由 Slurm 调度到计算节点，
在那里通过 Native / Conda / Apptainer 执行。两件事不要混淆。

形态决策见 [ADR-0005](../docs/decisions/0005-deployment-topology.md)。

## 一. 本机演示

```bash
cp .env.example .env
# 编辑 .env，至少填上 POSTGRES_PASSWORD
docker compose up -d --build
```

打开 <http://127.0.0.1:8107>。

想要一份可以立刻点的演示数据，在 `.env` 里设 `WORKSPACE107_SEED_DEMO=true`
再启动。

停止与清理：

```bash
docker compose down          # 停止，保留数据
docker compose down -v       # 停止并删除数据卷
```

## 二. 拓扑

```text
浏览器
   │  :8107
   ▼
 web (nginx, 非 root, :8080)
   ├── /            前端静态资源
   └── /api  ──────► api (uvicorn, 非 root, :8000)
                        │
                        ▼
                     db (PostgreSQL)
```

前后端同源，所以生产环境不需要 CORS。后端的 CORS 中间件只在
`WORKSPACE107_ENV=local` 时挂载。

api 容器启动时会依次执行：

```text
alembic upgrade head              升级数据库结构
python -m workspace107.tools.seed 载入平台目录（幂等）
uvicorn ...                       拉起服务
```

平台目录（运行环境、算力方案）是应用能工作的前提——没有算力方案就建不了运行方案。
它本应由平台管理后台维护（设计稿 §2.13 E），那部分还没做，
启动时载入是这期间的过渡方案。

## 三. 配置

全部通过环境变量注入，清单见仓库根目录的 [`.env.example`](../.env.example)。
容器部署要关注的几项：

| 变量 | 说明 |
| :--- | :--- |
| `POSTGRES_PASSWORD` | **必填**，不填 compose 直接报错退出 |
| `WORKSPACE107_HTTP_PORT` | 对外端口，默认 8107 |
| `WORKSPACE107_SCHEDULER` | `mock` 或 `slurm` |
| `WORKSPACE107_STORAGE_MOUNT` | Run 工作目录的挂载来源，见第五节 |
| `WORKSPACE107_SEED_DEMO` | 是否额外载入演示 Project |
| `WORKSPACE107_SLURM_JWT` | **等价于密码**，只从环境注入 |
| `WORKSPACE107_LOG_FORMAT` | `auto` / `json` / `text`，容器里默认输出 JSON |
| `WORKSPACE107_MAX_REQUEST_BYTES` | 请求体上限，默认 128 MB，应与 nginx 的 `client_max_body_size` 对齐 |
| `WORKSPACE107_MAX_FILE_BYTES` | 单个 Project 文件上限，默认 32 MB |

镜像里不含任何凭据。`.env` 同时被 `.gitignore` 和 `.dockerignore` 排除。

## 四. mock 调度器不能对外

默认的 `WORKSPACE107_SCHEDULER=mock` 会在 **api 容器内部**以子进程执行用户命令。

这意味着：**任何能提交 Run 的人都能在 api 容器里执行任意命令。**

它的用途是演示和内部试用——不连集群也能跑通完整闭环。
对外提供服务必须切换到 `slurm`。容器启动时也会在日志里打这条警告。

## 五. 接真实 107 集群

### 5.1 存储必须是共享文件系统

这是最容易踩的坑。换成 Slurm 之后，文件流向是：

```text
api 容器          准备 Run 工作目录，写入代码和输入
   │
   ▼
Slurm 计算节点     执行作业，读工作目录，写 stdout / stderr 和产物
   │
   ▼
api 容器          回来读日志、收集 Artifact
```

两边必须看到**同一份文件系统**。Docker 命名卷只在本机可见，
计算节点看不到，作业会立刻失败。

所以要把 `WORKSPACE107_STORAGE_MOUNT` 指向集群共享存储的挂载点：

```dotenv
WORKSPACE107_STORAGE_MOUNT=/public/workspace107/storage
```

并确认三件事：

1. 运行 docker 的主机上，这个路径确实挂载了共享存储
2. 计算节点上同一路径可见，且**路径字符串完全一致**（作业脚本里写的是绝对路径）
3. 目录属主与容器内的运行用户对得上——镜像里的 uid/gid 固定为 `10001:10001`

```bash
sudo mkdir -p /public/workspace107/storage
sudo chown -R 10001:10001 /public/workspace107/storage
```

具体路径和配额策略以平台实际配置为准，需要向平台方确认。

### 5.2 Slurm 接入

```dotenv
WORKSPACE107_SCHEDULER=slurm
WORKSPACE107_SLURM_API_BASE_URL=https://<集群 Slurm REST 地址>
WORKSPACE107_SLURM_API_USER=<提交作业的账号>
WORKSPACE107_SLURM_JWT=<从集群获取的 JWT>
```

注意事项：

- 当前适配器按 Slurm REST API **v0.0.40** 编写。接入前要确认目标集群实际启用的
  API 版本，字段和路径可能不同
- JWT 有有效期，过期后所有提交会失败。轮换机制属于后续工作
- api 容器要能通过网络访问 Slurm REST 端点

### 5.3 平台目录要换成真实值

种子数据里的分区（`debug` / `cpu` / `gpu`）、Account、QoS 和资源上限
**都是演示值**。接入真实集群前必须按平台实际配置调整
`compute_plans` 表，否则提交上去会被 Slurm 拒绝。

同样地，运行环境里的镜像路径要换成集群上真实存在的 `.sif` 文件。
这部分在 RuntimeBackend 补齐后（见
[ADR-0004](../docs/decisions/0004-runtime-backend.md)）会更完整。

### 5.4 认证

`WORKSPACE107_AUTH_MODE=dev` 用 `X-User` 请求头识别身份，**任何人都能冒充任何人**。
对外服务前必须换成学校统一身份认证——实现上只需替换
`backend/src/workspace107/api/deps.py` 里的 `get_current_user`。

## 六. 运维

```bash
docker compose ps                        # 各容器状态与健康检查
docker compose logs -f api               # 跟踪后端日志
docker compose exec api alembic current  # 当前数据库版本
docker compose exec api alembic history  # 迁移历史
```

### 6.1 两个探针的区别

```text
GET /api/v1/health   进程活着吗。不检查任何依赖，不会因为数据库抖动而失败
GET /api/v1/ready    依赖都通吗。数据库连不上返回 503
```

容器的 HEALTHCHECK 用的是 `/ready`——compose 靠它决定什么时候放前端进来，
数据库还没通就接流量只会让用户看到一堆 500。

如果以后上编排系统：`/health` 对应 liveness（决定要不要重启），
`/ready` 对应 readiness（决定要不要转流量）。两个混用会导致数据库短暂抖动
就把容器反复重启，比不检查还糟。

### 6.2 按 request_id 追一次请求

每个响应都带 `X-Request-Id`，错误响应体里也有同一个值：

```json
{
  "code": "preflight_rejected",
  "message": "提交前检查未通过：…",
  "problems": ["…"],
  "request_id": "req_9f2c1a83b4d5e6f70189"
}
```

用户报问题时把这个值一起给出来，然后：

```bash
docker compose logs api | grep req_9f2c1a83b4d5e6f70189
```

就能看到这次请求做了什么、在哪一步失败。日志在容器里是 JSON 单行格式，
接了日志系统之后可以直接按 `request_id` 字段检索。

上游网关如果已经生成了标识，通过 `X-Request-Id` 传进来会被沿用，
这样能跨服务串联同一次请求。

载入演示数据（已经起来之后再补）：

```bash
docker compose exec api python -m workspace107.tools.seed --demo
```

备份数据库：

```bash
docker compose exec -T db pg_dump -U workspace107 workspace107 > backup.sql
```

数据库 dump 含用户数据，**不要提交到仓库**。

升级：

```bash
git pull
docker compose up -d --build     # 重建镜像，启动时自动跑迁移
```

迁移是在 api 容器启动时执行的，**升级前先备份数据库**。

## 七. 上线前检查

- [ ] `POSTGRES_PASSWORD` 是随机生成的强密码，不是示例值
- [ ] `WORKSPACE107_SCHEDULER=slurm`，不是 mock
- [ ] `WORKSPACE107_AUTH_MODE` 已换成统一身份认证
- [ ] `WORKSPACE107_ENV=production`
- [ ] `WORKSPACE107_STORAGE_MOUNT` 指向共享存储，且计算节点上路径一致
- [ ] 算力方案里的分区、Account、QoS 与集群实际配置一致
- [ ] `.env` 没有被提交（`git status` 干净）
- [ ] 数据库有备份方案
- [ ] 如果不希望公开接口文档，删掉 `frontend/nginx.conf` 里 `/docs` 那段
- [ ] 前面加了 HTTPS 终结（compose 只提供 HTTP）
- [ ] `WORKSPACE107_MAX_REQUEST_BYTES` 与 nginx 的 `client_max_body_size` 对齐
- [ ] 日志已接入采集，能按 `request_id` 检索

## 八. 这里没有做什么

| 没做 | 说明 |
| :--- | :--- |
| HTTPS | 由前置反代或网关处理 |
| 多副本与负载均衡 | 迁移在容器启动时执行，前提是单实例；多副本要先把迁移拆出去 |
| 日志收集与监控 | 有结构化日志和 request_id，但没有采集、指标和告警 |
| 接口限流 | 单实例可以在进程内做，多实例需要共享状态（Redis），留到后续阶段 |
| 数据库自动备份 | 需要按运行环境接入现有备份方案 |
| K8s 编排 | 见 ADR-0005 的「影响」一节 |
