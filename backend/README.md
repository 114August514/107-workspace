# 后端

107 Workspace 的 FastAPI 服务。模块化单体，依赖方向单向：

```text
api  →  application  →  domain ports  ←  infrastructure
```

## 目录

```text
src/workspace107/
├── domain/           领域对象、枚举、规则、端口定义（不依赖框架）
│   ├── models.py         可变对象与不可变版本
│   ├── run_snapshot.py   不可变执行事实（GR-202）
│   ├── secrets.py        环境变量表达式与 Secret 引用（GR-304）
│   ├── compute.py        算力方案、请求与调度解析
│   └── ports/            ProjectContent / Scheduler / Storage / Repositories 等端口
├── application/      用例编排、权限校验、事务边界
│   ├── access.py         AccessGuard（GR-101 / GR-102 / GR-103）
│   ├── run_service.py    请求事务内固定 Snapshot、QUEUED Run 与执行意图
│   └── run_worker.py     独立恢复、调度同步与 Artifact finalization
├── infrastructure/   系统 Git、Shared FS workspace、SQLAlchemy 与 Scheduler 适配器
├── api/              路由与 schema，不写业务规则
├── tools/            OpenAPI 导出、种子数据
├── main.py           API 装配入口
└── worker.py         Independent Worker 装配与进程入口
```

## 依赖注入

API 与 Worker 是两个组合入口，业务代码只依赖 domain ports：

```text
domain/ports/     用 Protocol 描述 Scheduler / Storage / Execution Store
application/      构造函数注入，只认这些协议
infrastructure/   实现协议
main.py           API：数据库、存储、时钟
worker.py         Worker：PostgreSQL 全局 advisory lock、存储、调度器
api/deps.py       请求级仓储与用例服务
```

路由通过 `Services` 容器拿用例服务，而 `Services` **只暴露 application 层的服务**——
拿不到仓储和端口，也就没办法绕过用例层。绕过用例层等于绕过权限校验、
事务边界和领域规则，所以这是一条安全边界，不是风格偏好。

需要新能力时：

```text
需要一种新的外部能力   → 先在 domain/ports/ 定义协议，再在 infrastructure/ 实现
需要一类新的操作       → 加用例服务，或给现有服务加方法
                        不要往 Services 容器里塞端口
```

API 不启动后台同步任务；Worker 持有一条 PostgreSQL session advisory lock 串行推进 Run。

完整 Worker 运行需要 Linux / WSL2、PostgreSQL 和 POSIX Shared FS 语义；原生 Windows
只保留 contributor API/Git 检查，不构造 Worker。权威矩阵见
[`ADR-0004`](../docs/decisions/0004-platform-support-matrix.md)。

## 安装与运行

```bash
uv sync --all-extras
uv run alembic upgrade head
uv run python -m workspace107.tools.seed
uv run uvicorn workspace107.main:create_app --factory --reload
uv run python -m workspace107.worker               # Linux / WSL2；需要 PostgreSQL
```

接口文档：<http://127.0.0.1:8000/docs>

## 配置

全部通过环境变量注入，变量清单见仓库根目录的 `.env.example`。
本地把它复制成 `backend/.env` 即可：

```bash
cp ../.env.example .env
```

关键项：

| 变量 | 说明 |
| :--- | :--- |
| `WORKSPACE107_DATABASE_URL` | 默认 SQLite；部署时改 PostgreSQL |
| `WORKSPACE107_STORAGE_ROOT` | Project Git repositories、Run 目录、日志和 Artifact 的根目录 |
| `WORKSPACE107_SCHEDULER` | `mock`（本机子进程真实执行）或 `slurm` |
| `WORKSPACE107_SLURM_JWT` | **等价于密码**，只能从环境注入 |
| `WORKSPACE107_AUTH_MODE` | `dev` 用 `X-User` 请求头识别用户 |

## 开发模式下的身份

`WORKSPACE107_AUTH_MODE=dev` 时用 `X-User` 请求头识别用户，
首次出现会自动建号并准备 Personal Workspace：

```bash
curl -H 'X-User: student' http://127.0.0.1:8000/api/v1/me
```

接入学校统一身份认证后只需替换 `api/deps.py` 中的 `get_current_user`。

## 调度适配器

| 适配器 | 行为 |
| :--- | :--- |
| `mock` | 在本机以子进程**真实执行**作业，状态来自真实退出码 |
| `slurm` | 通过 Slurm REST API 提交，状态来自 Slurm |

两者实现 `submit/find_by_correlation/poll/cancel`，没有「标记成功」入口。Mock 可在本地按完整
correlation 权威查询；Slurm correlation 尚未经目标环境核验时返回 incomplete，Worker
保持 Run 待恢复且绝不盲目重提。

Mock 模式下会把渲染出的 sbatch 脚本写到 `var/storage/runs/<run_id>/job.sh`，
用户可以直接看到平台替他生成了什么。

## 迁移

```bash
uv run alembic upgrade head                       # 应用到最新
uv run alembic revision --autogenerate -m "说明"  # 改了 tables.py 之后
uv run alembic downgrade -1                       # 回退一步
```

迁移文件必须提交。

## 测试

```bash
uv run pytest                              # 当前活动测试
uv run pytest tests/unit                   # 纯领域与 Application 单元测试
uv run pytest tests/integration            # 单个 Adapter 的集成测试
uv run pytest tests/architecture           # 仓库与文档约束
uv run ruff check . && uv run ruff format --check .
```

当前测试基线：

```text
tests/unit/domain/          纯领域规则与不变量
tests/unit/application/     不接真实基础设施的用例逻辑
tests/unit/observability/   请求标识上下文与日志格式化
tests/integration/storage/  本地存储与配置行为
tests/integration/scheduler/ Mock Scheduler 平台适配
tests/architecture/         依赖方向、活动文档和仓库引用约束
```

旧 ASGI / SQLite 产品流程测试已经退出活动基线，不能把当前测试数量理解为目标架构覆盖率。
完整粒度、未来目录和覆盖率策略见 [`../docs/testing/README.md`](../docs/testing/README.md)。
在仓库根目录运行 `make coverage` 生成报告；重构期不设失真的全仓百分比门槛。

## 接口契约

改了 DTO 或路由之后必须在仓库根目录重新生成契约和前端类型，否则统一检查会失败：

```bash
make contract
```

它会依次导出 `contracts/openapi.json` 和 `frontend/src/api/schema.d.ts`，
两个生成物都要提交。前端所有类型从后者派生，所以**后端改一个字段，
前端受影响的地方会在类型检查时全部报出来**。

写 DTO 时让契约说实话，生成的类型才有约束力：

- 是枚举就写成枚举（`status: RunStatus`），不要写 `str`
- 结构固定就定义模型，不要用 `dict[str, object]`
- 可以不传的字段写 `X | None = None`，不要用空字符串当默认值
- 新增的错误类型记得在 `api/routes/__init__.py` 的 `COMMON_ERRORS` 里体现
