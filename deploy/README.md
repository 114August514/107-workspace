# 部署

这里说明当前 107 Workspace 应用容器的运行方式，以及它距离真实集群部署还差什么。
容器编排是开发和受信任演示基线，不代表生产验收已经完成。

## 本机演示

```bash
cp .env.example .env
# 编辑 .env，至少设置 POSTGRES_PASSWORD
docker compose up -d --build
```

打开 <http://127.0.0.1:8107>。停止服务但保留数据：

```bash
docker compose down
```

`docker compose down -v` 会删除数据库和存储卷，只能在明确不需要其中数据时执行。

## 拓扑

```text
browser :8107
      |
      v
web (nginx :8080)
      | /api
      v
api (uvicorn :8000) ---> db (PostgreSQL)
      |
      +-- local/shared storage
      +-- mock process or slurmrestd
```

API 容器启动时会执行 Alembic 升级和幂等的平台目录 seed，然后启动应用。该流程假设
单个 API 实例；扩展到多副本之前，必须把迁移拆成独立的一次性任务。

## 关键配置

完整变量和默认值见 [`.env.example`](../.env.example)。

| 变量 | 说明 |
| :--- | :--- |
| `POSTGRES_PASSWORD` | 必填，不得使用可猜测的默认值 |
| `WORKSPACE107_HTTP_PORT` | Web 暴露端口，默认 `8107` |
| `WORKSPACE107_SCHEDULER` | `mock` 或 `slurm` |
| `WORKSPACE107_STORAGE_MOUNT` | API 与计算节点需要共同看到的存储来源 |
| `WORKSPACE107_SLURM_API_BASE_URL` | slurmrestd 地址 |
| `WORKSPACE107_SLURM_API_USER` | Slurm API 用户 |
| `WORKSPACE107_SLURM_JWT` | 等价于密码，只能从环境注入 |
| `WORKSPACE107_AUTH_MODE` | `dev` 仅用于本地；真实部署必须替换 |

镜像不包含凭据，`.env` 也不会进入 Git 或构建上下文。

## Mock 不是沙箱

`WORKSPACE107_SCHEDULER=mock` 会在 API 进程所在主机或容器中，通过宿主 shell 真实
执行 Run Configuration 的命令。任何能提交 Run 的用户都能执行该运行身份允许的
命令，因此它只能用于本地开发、自动化测试和受信任演示，不能对不受信任用户开放。

Windows 下 Mock 使用系统命令解释器，POSIX 下使用 Bash。命令本身是否跨平台仍由
Project 负责；平台不会自动翻译 shell 语法。

## 接入真实集群

当前代码包含 Slurm REST 适配器，但尚未在真实 107 集群完成版本、认证、网络和状态
映射验收。切换配置不等于完成接入。

### 共享存储

API 负责准备 Run 目录并读取日志和 Artifact，计算节点负责实际执行。两侧必须看到
同一绝对路径：

```text
api writes Run directory
        |
        v
shared filesystem
        ^
        |
compute node reads/writes it
```

Docker 命名卷只在单机 Docker 内可见，不满足真实 Slurm 计算节点的要求。真实接入时
应把 `WORKSPACE107_STORAGE_MOUNT` 设置为已经挂载的共享文件系统路径，并验证：

1. API 主机和计算节点看到完全相同的路径字符串。
2. API 容器 UID/GID `10001:10001` 与共享目录权限匹配。
3. 只读 Input Binding 在目标文件系统和运行身份下确实不可修改。
4. 日志与 Artifact 的并发写入、清理和失败恢复行为符合平台要求。

### Slurm 与运行环境

```dotenv
WORKSPACE107_SCHEDULER=slurm
WORKSPACE107_SLURM_API_BASE_URL=https://<slurmrestd>
WORKSPACE107_SLURM_API_USER=<user>
WORKSPACE107_SLURM_JWT=<secret>
```

接入前还必须确认 slurmrestd API 版本、JWT 生命周期、分区、Account、QoS、资源上限
和错误响应。seed 中的计算方案与环境值是开发数据，不是 107 平台配置事实。

现有实现也没有独立 Background Worker、Git 版本存储和 Apptainer 准备链路；这些是
`DESIGN-final.md` M1 Walking Skeleton 的缺口，不能由 API 容器或 Mock 路径代替。

## 探针和排障

```text
GET /api/v1/health   只判断进程是否响应
GET /api/v1/ready    检查数据库是否可用
```

响应头和错误体包含 `request_id`。排障时记录它，并在 API 日志中按同一值检索。

常用命令：

```bash
docker compose ps
docker compose logs -f api
docker compose exec api alembic current
docker compose exec api alembic history
```

## 上线前最低条件

- 使用强随机数据库密码，并确保 `.env` 未提交。
- 不向不受信任用户开放 Mock 调度器或 `dev` 身份模式。
- 完成真实 Slurm、共享存储、运行时和认证的环境验收。
- 将 seed 中的演示算力与环境目录替换为平台事实。
- 建立数据库和用户存储的备份、恢复、保留与清理流程。
- 在前置网关启用 HTTPS、访问控制、限流和日志采集。
- 验证 API 请求体上限与 nginx `client_max_body_size` 一致。
- 多副本部署前拆分数据库迁移和后台状态同步职责。

当前 Compose 没有提供 HTTPS、自动备份、多副本编排、监控告警或生产级 Secret
管理。这些缺口必须显式完成，不能依赖默认配置补齐。
