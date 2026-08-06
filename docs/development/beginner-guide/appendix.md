# 附录：常用速查

## A.1 术语速查

| 术语 | 一句话含义 |
| --- | --- |
| Workspace | 协作、资源归属和权限边界 |
| Membership | User 在 Workspace 中的成员关系和角色 |
| Project | 项目文件、版本、配置和运行记录的容器 |
| Project Version | 已发布且不可原地修改的项目内容版本 |
| Run Configuration | 可编辑、可复用的运行方案 |
| Run Snapshot | Run 创建时固定的不可变执行事实 |
| Environment | 代码运行的软件基础 |
| Shared Resource | Workspace 获准使用的共享内容 |
| Input Binding | Run 对某个内容版本的只读绑定 |
| Compute Plan | 平台提供的算力方案 |
| Resource Entitlement | Workspace 使用算力方案的有效资格 |
| Scheduler | 提交、查询和取消计算作业的系统边界 |
| Artifact | Run 结束后收集的结果文件 |
| Variable | 可公开展示的普通配置值 |
| Secret | 需要受控保存和解析的敏感配置 |
| Port | Domain 定义的外部能力协议 |
| Adapter | 某种环境下对 Port 的具体实现 |

术语有歧义时以 `docs/product/design.md` 的统一领域语言为准。

## A.2 目录速查

```text
backend/src/workspace107/
├── api/                 HTTP 路由、Schema、依赖和错误转换
├── application/         用例、权限和事务编排
├── domain/              模型、规则、枚举和 Port
├── infrastructure/      DB、Storage、Scheduler 等 Adapter
├── tools/               OpenAPI 导出和 Seed
├── main.py              应用装配入口
└── config.py            环境变量配置

frontend/src/
├── api/                 API Client 与生成类型
├── components/          业务和公共组件
├── pages/               顶层页面
└── utils/               纯展示和判断函数
```

## A.3 日常命令

| 命令 | 作用 |
| --- | --- |
| `make doctor` | 检查开发环境 |
| `make setup` | 安装前后端依赖 |
| `make dev` | 启动前后端开发服务 |
| `make migrate` | 数据库升级到最新版本 |
| `make migrate-down` | 数据库回退一步 |
| `make test` | 运行活动测试 |
| `make check-backend` | 后端检查 |
| `make check-frontend` | 前端检查 |
| `make contract` | 更新 OpenAPI 与前端类型 |
| `make contract-check` | 核对接口生成物 |
| `make coverage` | 生成后端覆盖率报告 |
| `make journal` | 查看在途工作 |
| `make check` | 提交前完整检查 |
| `make compose-up` | 启动 Compose 演示 |
| `make compose-down` | 停止 Compose 演示 |

查看所有任务和参数：

```bash
make help
```

Windows 没有 Make 时，将目标传给公共入口，例如：

```powershell
uv run --no-project python scripts/workspace.py check frontend
```

## A.4 本地地址

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:5173` | 前端开发服务器 |
| `http://127.0.0.1:8000/docs` | FastAPI 交互式接口文档 |
| `http://127.0.0.1:8000/api/v1/health` | API 进程健康检查 |
| `http://127.0.0.1:8000/api/v1/ready` | 数据库就绪检查 |
| `http://127.0.0.1:8107` | Compose 演示入口 |

## A.5 常见 HTTP 状态码

| 状态码 | 在本项目中通常表示 |
| --- | --- |
| 200 | 查询或操作成功 |
| 201 | 资源创建成功 |
| 400 | 请求语义不成立 |
| 403 | 资源可见，但没有操作能力 |
| 404 | 资源不存在或调用者无发现权限 |
| 409 | 状态或唯一约束冲突 |
| 413 | 请求体或上传文件过大 |
| 422 | 请求字段未通过 Schema 校验 |
| 500 | 未处理的服务端错误 |
| 502 | 外部调度等依赖返回错误 |

具体接口可能只声明其中一部分，以 OpenAPI 契约为准。

## A.6 配置速查

| 变量 | 作用 |
| --- | --- |
| `WORKSPACE107_DATABASE_URL` | 数据库地址 |
| `WORKSPACE107_STORAGE_ROOT` | 文件存储根目录 |
| `WORKSPACE107_SCHEDULER` | `mock` 或 `slurm` |
| `WORKSPACE107_SLURM_API_BASE_URL` | slurmrestd 地址 |
| `WORKSPACE107_SLURM_API_USER` | Slurm API 用户 |
| `WORKSPACE107_SLURM_JWT` | Slurm API 凭据，等价于密码 |
| `WORKSPACE107_AUTH_MODE` | 身份模式，本地为 `dev` |
| `WORKSPACE107_RUN_SYNC_INTERVAL_SECONDS` | Run 后台同步间隔 |

完整清单和默认值看仓库根目录 `.env.example`。真实值不得写入文档、Issue 或 Git。

## A.7 Run 排障路径

```text
提交按钮是否成功
  ↓
浏览器请求、状态码、request_id
  ↓
Application 是否完成权限和 preflight
  ↓
是否生成 Run Snapshot 和运行目录
  ↓
Scheduler 是否返回 scheduler_job_id
  ↓
poll 返回什么状态和退出码
  ↓
日志是否写入，必需 Artifact 是否存在
  ↓
前端是否读取并正确展示最新状态
```

Mock 问题不要直接推断为 Slurm 问题；Slurm 问题也不要通过手改数据库状态绕过。

## A.8 提交前检查

```text
[ ] 术语与产品设计一致
[ ] 资源查询包含归属边界
[ ] Version 和 Snapshot 没有原地更新
[ ] Secret 明文没有进入 API、日志、快照或 Diff
[ ] 测试先失败过，并验证了用户可观察结果
[ ] API 变化已重新生成契约
[ ] 没有新增未经同意的依赖或迁移
[ ] make check 已实际通过
[ ] git diff 只包含本次任务
[ ] PR 记录了验证证据和未验证范围
```

## A.9 继续阅读

遇到具体问题时按责任选择活动文档：

- 产品术语和规则：`docs/product/design.md`
- 后端实现入口：`backend/README.md`
- 前端实现入口：`frontend/README.md`
- 测试策略：`docs/testing/README.md`
- Git 与协作：`docs/contributing/git-workflow.md`
- 部署与真实集群边界：`docs/operations/deployment.md`
- 接口契约：`contracts/README.md`
- 高影响设计理由：`docs/decisions/`

历史目录只用于追溯，不能替代这些活动事实来源。

