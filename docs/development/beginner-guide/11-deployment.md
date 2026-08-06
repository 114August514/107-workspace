# 第十一章：容器、部署及其边界

当前 Compose 是本机开发和受信任演示基线，不是生产方案。本章帮助开发者理解容器中的服务
关系，并明确哪些结论不能从本机演示推出。

## 11.1 四个 Docker 概念

- **Image**：包含应用和运行依赖的只读模板。
- **Container**：Image 启动后的进程和隔离环境。
- **Volume**：独立于容器生命周期保存的数据。
- **Network**：让 Compose 服务按服务名互相访问的网络。

后端和前端各自维护 Dockerfile，`deploy/compose.yaml` 描述它们怎样与数据库组合。

## 11.2 Compose 拓扑

```text
浏览器 :8107
    |
web（nginx :8080）
    | /api
api（FastAPI :8000）----> db（PostgreSQL）
    |
    +----> storage
    +----> Mock 子进程或 slurmrestd
```

浏览器只访问 web 暴露的端口。nginx 提供前端静态文件，并把 `/api` 转发到 API。数据库不直接
暴露给浏览器。

## 11.3 启动本机演示

复制根目录配置并设置数据库密码：

```bash
cp .env.example .env
# 编辑 .env，设置强随机 POSTGRES_PASSWORD
make compose-config
make compose-build
make compose-up
```

访问 <http://127.0.0.1:8107>。停止并保留数据：

```bash
make compose-down
```

带 `-v` 的 Compose Down 会删除数据库和存储卷，只有明确不需要数据时才能使用。真实 `.env`
不得提交。

## 11.4 启动和健康检查

API 容器会执行 Alembic 升级和幂等 Seed，然后启动 Uvicorn。这个流程假设只有一个 API 实例；
扩展多副本前必须把迁移和后台同步拆成独立职责。

Compose 使用数据库和 API 健康检查控制启动顺序。排障命令包括：

```bash
docker compose --project-directory . --file deploy/compose.yaml ps
docker compose --project-directory . --file deploy/compose.yaml logs -f api
docker compose --project-directory . --file deploy/compose.yaml exec api alembic current
```

直接调用 Docker Compose 排障时应始终指定项目目录和清单路径，避免从错误目录加载另一份配置。

## 11.5 配置和 Secret

Compose 把 PostgreSQL 地址、Storage 路径、Scheduler 和身份模式等变量注入 API。镜像不包含
凭据。服务凭据和 Workspace Secret 是两类不同数据，但都不能出现在源码、镜像或日志中。

当前数据库 Secret Vault 是开发实现，完整生产环境仍需要专门 Secret 管理。日志接口会遮盖
已知 Secret，但这不能替代从产生源头防止敏感值写入原始文件。

## 11.6 为什么还不是生产部署

当前方案没有提供：

- HTTPS 和正式身份认证；
- 自动备份、恢复和数据保留流程；
- 多副本编排及职责拆分；
- 监控、告警、限流和完整日志采集；
- 生产级 Secret 管理；
- 真实 Slurm、共享存储和 Apptainer 验收。

此外，`dev` 身份会信任用户给出的 `X-User`，Mock Scheduler 会执行用户命令。二者都不能向
不受信任用户开放。

## 11.7 接入真实集群前的最低验证

开发者不负责独自完成集群上线，但应知道关键依赖：

1. slurmrestd 版本、认证、网络和状态映射通过验收；
2. Partition、Account、QoS、GPU 和额度来自真实平台配置；
3. API 与计算节点以同一绝对路径访问共享存储；
4. 运行身份、UID/GID 和只读输入权限正确；
5. 日志、Artifact、失败恢复和清理流程经过端到端测试；
6. 真实认证、HTTPS、备份、监控和 Secret 管理到位。

切换 `WORKSPACE107_SCHEDULER=slurm` 只是配置动作，不是完成上述验收的证据。

