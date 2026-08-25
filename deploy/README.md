# 部署文件

本目录保存可执行编排。通用拓扑、配置和排障见
[`docs/operations/deployment.md`](../docs/operations/deployment.md)；目标 107 当前证据边界和人工门见
[`docs/operations/107-cluster.md`](../docs/operations/107-cluster.md)。

[`compose.yaml`](compose.yaml) 只用于 Linux/WSL2 本地开发和受信任演示，不提供 HTTPS、生产
Secret 管理、自动备份、多副本编排或监控告警，因此不是生产部署方案。原生 Windows /
PowerShell runtime 不受支持；平台矩阵见
[ADR-0005](../docs/decisions/0005-platform-support-matrix.md)。

## 目录边界

- `deploy/` 管理服务如何组合。
- [`backend/Dockerfile`](../backend/Dockerfile) 与
  [`backend/docker-entrypoint.sh`](../backend/docker-entrypoint.sh) 管理后端 image/bootstrap。
- 环境模板在 [`.env.example`](../.env.example)；真实 credential 不得提交。
- 只有实际引入其他部署方式时才增加目录，不预建 provider framework。

## Compose 契约

Compose 表达一个 API、一个独立 Worker、PostgreSQL、Web 和共享 storage。API/Worker 对 storage
使用同一固定容器路径；Worker 直接依赖 PostgreSQL，不依赖 API。Scheduler、Slurm profile、JWT、
shared GID 和 Worker poll 配置只属于 Worker，API 环境禁止出现这些变量。

本地 image identity 和 shared GID 默认为 `10001`。可以通过 `.env` 的 service UID/GID build args
和 shared GID 重建/配置，但真实 107 service/compute identity、mount mapping 和权限必须人工验收；
清单可配置不等于目标环境 accepted。

## 统一入口

在仓库根目录运行：

```bash
make compose-config
make compose-build
make compose-up
make compose-down
```

`compose-config` 不只渲染 YAML，还检查 API/Worker credential boundary、Worker 所需配置、单独 DB
依赖和 Worker healthcheck。Makefile 是薄转发，任务实现位于 `scripts/workspace.py`。

直接排障时仍须显式指定项目目录与清单：

```bash
docker compose --project-directory . --file deploy/compose.yaml ps
docker compose --project-directory . --file deploy/compose.yaml logs -f api worker
```
