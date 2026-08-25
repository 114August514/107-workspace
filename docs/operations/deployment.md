# 部署

这里说明当前 107 Workspace executable skeleton 的容器运行方式。Compose 是 Linux/WSL2
本地开发和受信任演示基线，不是生产或真实 107 验收。清单入口见
[`deploy/README.md`](../../deploy/README.md)，目标集群门见 [`107-cluster.md`](107-cluster.md)。
平台边界以 [ADR-0005](../decisions/0005-platform-support-matrix.md) 为准。

## 本机演示

```bash
cp .env.example .env
# 至少设置 POSTGRES_PASSWORD
make compose-config
make compose-build
make compose-up
```

打开 <http://127.0.0.1:8107>。`make compose-down` 停止服务并保留数据。直接执行
`docker compose ... down -v` 会删除数据库与 storage volume，只能在明确不需要数据时使用。

## 拓扑与责任

```text
browser -> web -> API ---------------------> PostgreSQL
                    |                            ^
                    | project/storage access     |
                    v                            | execution intent/state
             canonical storage <---------- Worker (replicas=1)
                                              |
                                              `-> MockScheduler or slurmrestd
```

API 启动时执行 Alembic migration 和幂等平台目录 seed；只有
`WORKSPACE107_SEED_DEMO=true` 才创建演示数据。该 bootstrap 假设单 API 实例，多副本前必须拆成
独立一次性任务。

Worker 是独立进程并直接依赖 PostgreSQL，不依赖 API health。它取得 session advisory lock 后一次
推进一个 execution intent。Compose 固定一个 Worker；这不是 standby、多副本或 lease 协议。

API 与 Worker 挂载同一 storage source 到固定容器路径
`/var/lib/workspace107/storage`。Scheduler、Slurm profile、JWT、shared GID 和 Worker poll 配置只
注入 Worker；API 服务不得接收这些变量或 credential。API 只持有请求、数据库、auth 和 storage
配置，不 submit 或 poll Scheduler。

## 配置

完整模板见 [`.env.example`](../../.env.example)。

| 变量 | 所属进程 | 说明 |
| :--- | :--- | :--- |
| `POSTGRES_PASSWORD` | DB/API/Worker connection | Compose 必填，无默认密码 |
| `WORKSPACE107_STORAGE_MOUNT` | API + Worker | 两者共享的 mount source |
| `WORKSPACE107_SERVICE_UID/GID` | image build | 本地默认 `10001:10001`；改值需重建镜像 |
| `WORKSPACE107_SHARED_GID` | Worker | Run tree 的 POSIX shared group；本地默认 `10001` |
| `WORKSPACE107_SCHEDULER` | Worker | `mock` 或 gated `slurm` |
| `WORKSPACE107_SLURM_*` | Worker only | 单 profile、correlation 和 secret；API 禁止注入 |
| `WORKSPACE107_AUTH_MODE` | API | `dev` 只用于本地 |
| `WORKSPACE107_SEED_DEMO` | API bootstrap | 仅本地/受信任演示 |

`.env` 不进入 Git 或 image build context。模板中的空 Slurm 值和本地 `10001` 默认故意不代表目标
107 mapping。真实 UID/GID、mount、profile 和 credential lifecycle 必须人工核验。

## Canonical storage 与权限

Docker named volume 只在单机 Docker 内可见，不满足真实计算节点。真实部署必须让 API、Worker
和 compute node 以**相同绝对路径**看到相同内容，并核验：

1. service UID/GID、compute UID/GID 和 shared GID；Worker 必须属于 shared group；
2. Run root 的 setgid/mode、compute traverse/write 范围、Artifact/control 区仅 service 可写；
3. Snapshot 绑定 Project Version 导出后不可漂移；Run Input 的 artifact/shared-resource/subpath
   必须保持只读和路径安全；
4. 同目录 staging-to-final atomic rename、并发 Log/Artifact 写入和进程重启恢复。

Compose 用 build args 配置 service identity，并用 `group_add` 给 Worker 加 shared GID；这些只表达
部署参数，不证明该 mapping 被 107 接受。若计算节点不能提供
`/var/lib/workspace107/storage`，必须先调整所有三方 mapping 并重新验收，不能只改 volume source。

## Mock 与官方 smoke

MockScheduler 在 **Worker 容器/主机**用 shell 真实执行命令，不是沙箱。它只允许 local/test，不能
向不受信任用户开放；production 环境选择 Mock 会在 Worker 配置阶段失败。

```bash
# 需要 WORKSPACE107_DATABASE_URL 指向可创建临时数据库的 PostgreSQL
make smoke
```

默认 smoke 每次创建唯一 PostgreSQL database 和临时 storage，执行 migration/seed，启动 API 与
独立 Worker，使用 MockScheduler 走 Project → immutable Git Version → Run Snapshot → Log →
Artifact，随后终止两个进程、drop 临时数据库并删除临时目录。它不复用或清理现有 Compose 数据。

要只检查已运行的栈而不接管生命周期：

```bash
uv run --no-project python scripts/workspace.py smoke \
  --base-url http://127.0.0.1:8107/api/v1
```

external smoke 会留下它创建的业务数据，调用者负责目标栈的数据治理。

## 接入真实 107

配置解析通过不等于接入完成。`docs/operations/107-cluster.md` 的 human gate 必须逐项产生 fresh、
脱敏 evidence，至少覆盖：

- service/compute identity、shared GID、canonical mount 和权限；
- REST version/profile、target cluster、路径、响应和状态映射；
- correlation 精确过滤权限、容量和分页完整性；
- credential issuer、TTL、Worker-only injection、renewal、revocation 与 restart lifecycle；
- Account/Partition/QoS/resources、Native setup，以及获授权 submit/restart ambiguity 验收。

当前没有多 profile/cluster、Apptainer、credential fallback 或自动生命周期 policy。任一事实未知就
保持 Mock，不登录、不 probe、不 submit。

## 探针和排障

```text
GET /api/v1/health   进程是否响应
GET /api/v1/ready    数据库是否可用
```

```bash
docker compose --project-directory . --file deploy/compose.yaml ps
docker compose --project-directory . --file deploy/compose.yaml logs -f api worker
docker compose --project-directory . --file deploy/compose.yaml exec api alembic current
```

响应头和错误体包含 `request_id`；排障时按同一值检索 API 日志。Worker 日志不得打印 credential。

## 上线前最低条件

- 使用强随机数据库密码，确保 `.env` 未提交；真实 Secret 只注入 Worker。
- 不向不受信任用户开放 Mock 或 dev auth。
- 完成 `107-cluster.md` 全部 human gate；没有 fresh evidence 不得声称真实链路通过。
- 建立 migration 单次执行、数据库/storage 备份恢复、保留清理、HTTPS、访问控制、限流、日志与
  监控告警。
- 继续保持 Worker 单副本；真实多 Worker 义务出现时先新增架构决策。

当前 Compose 不提供 HTTPS、自动备份、多副本编排、生产 Secret 管理或真实 107 credential
lifecycle。这些缺口必须显式完成，不能依赖默认配置补齐。
