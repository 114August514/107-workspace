# 部署文件

本目录保存可执行的部署编排；部署原理、生产边界和排障说明仍以
[`docs/operations/deployment.md`](../docs/operations/deployment.md) 为准。

当前只有 [`compose.yaml`](compose.yaml)，用于本机开发和受信任演示。它不提供 HTTPS、
生产级 Secret 管理、自动备份、多副本编排或监控告警，因此不构成生产部署方案。

## 目录边界

- `deploy/` 管理服务如何组成一个可运行环境。
- [`backend/Dockerfile`](../backend/Dockerfile) 与
  [`backend/docker-entrypoint.sh`](../backend/docker-entrypoint.sh) 由后端镜像维护。
- [`frontend/Dockerfile`](../frontend/Dockerfile) 与
  [`frontend/nginx.conf`](../frontend/nginx.conf) 由前端 Web 镜像维护。
- 环境变量模板保留在根目录 [`.env.example`](../.env.example)，真实凭据不得提交。

只有在实际引入 Kubernetes、Systemd 或其他部署方式时，才在本目录增加对应子目录；
不要预先建立空目录或复制服务自己的构建文件。

## 统一入口

部署拓扑只支持 Linux / WSL2；原生 Windows 不承担 M1 Worker、Shared FS、smoke 或部署。
权威平台矩阵见 [ADR-0004](../docs/decisions/0004-platform-support-matrix.md)。

在仓库根目录运行：

```bash
make compose-config
make compose-build
make compose-up
make compose-down
```

统一入口会显式选择本目录的 Compose 文件，并保持相对路径以仓库根目录为基准。
需要直接使用 Docker 排障时，也必须指定项目目录和清单路径：

```bash
docker compose --project-directory . --file deploy/compose.yaml ps
```
