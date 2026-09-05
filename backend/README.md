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
│   └── ports/            Scheduler / Storage / SecretVault / Repositories / Clock
├── application/      用例编排、权限校验、事务边界
│   ├── access.py         AccessGuard（GR-101 / GR-102 / GR-103）
│   ├── run_service.py    提交前检查、创建 Run、重跑、取消
│   └── run_lifecycle.py  调度状态同步与 Artifact 收集
├── infrastructure/   端口实现：SQLAlchemy 仓储、本地存储、Mock/Slurm 调度
├── api/              路由与 schema，不写业务规则
├── tools/            OpenAPI 导出、种子数据
└── main.py           唯一的装配点
```

## 依赖注入

当前旧实现只在两个组合入口里构造具体实现，别处一律拿协议：

```text
domain/ports/     用 Protocol 描述「需要什么能力」
application/      构造函数注入，只认这些协议
infrastructure/   实现协议
main.py           进程级装配：数据库引擎、存储、调度器、时钟
api/deps.py       请求级装配：仓储、Secret 保管、各用例服务
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

这两处入口是当前代码事实，不是未来组合根数量门禁。目标架构还需要独立 Worker 入口；
依赖方向和未来模块边界以 `docs/product/design.md` 为准。

## 安装与运行

```bash
uv sync --all-extras
uv run alembic upgrade head
uv run python -m workspace107.tools.seed
uv run uvicorn workspace107.main:create_app --factory --reload
```

`seed` 不带参数时只幂等创建本地开发 Compute Plans，不创建 Environment 或 Shared
Resource。显式演示 bootstrap 使用：

```bash
uv run python -m workspace107.tools.seed --demo
uv run python -m workspace107.tools.seed --demo --platform-owner-username <username>
```

Owner 选择顺序是 CLI、`WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME`、`platform-admin`，且只在
`grp_platform_assets` 首次不存在时生效。组已存在时仍确保账密管理员 User 存在，尚未加入则补为
管理员，不改已有 Owner。演示 Project 使用 `grp_demo` 自己的 Environment；它与
`grp_platform_assets` 持有的两条平台演示 Environment 是不同资产。这不是 production
provisioning 接口。

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
| `WORKSPACE107_STORAGE_ROOT` | Project 文件、Run 目录、日志和 Artifact 的根目录 |
| `WORKSPACE107_SCHEDULER` | `mock`（本机子进程真实执行）或 `slurm` |
| `WORKSPACE107_SLURM_JWT` | **等价于密码**，只能从环境注入 |
| `WORKSPACE107_AUTH_MODE` | `dev` 用 `X-User` 请求头识别用户，缺省 `student`，没有登录页；`ustc` 只接受反向代理注入的身份，见 [`docs/operations/authentication.md`](../docs/operations/authentication.md) |

## 开发模式下的身份

`WORKSPACE107_AUTH_MODE=dev` 时用 `X-User` 请求头识别用户。首次出现只建立 User 身份，
不创建额外 ownership 容器：

```bash
curl -H 'X-User: student' http://127.0.0.1:8000/api/v1/me
curl -X POST -H 'X-User: student' -H 'Content-Type: application/json' \
  -d '{"name":"计算物理课题组","description":""}' \
  http://127.0.0.1:8000/api/v1/user-groups
```

公开登录页不走这条 `dev` 路径，见 [`deploy/cas-revproxy/README.md`](../deploy/cas-revproxy/README.md)。

## 调度适配器

| 适配器 | 行为 |
| :--- | :--- |
| `mock` | 在本机以子进程**真实执行**作业，状态来自真实退出码 |
| `slurm` | 通过 Slurm REST API 提交，状态来自 Slurm |

两者都只实现 `submit` / `poll` / `cancel`，没有「标记成功」的入口——
当前实现中，Run 状态只能由调度系统的轮询结果驱动。

Mock 模式下会把渲染出的 sbatch 脚本写到 `var/storage/runs/<run_id>/job.sh`，
用户可以直接看到平台替他生成了什么。

## 迁移

```bash
uv run alembic upgrade head                       # 应用到最新
uv run alembic revision --autogenerate -m "说明"  # 改了 tables.py 之后
uv run alembic downgrade -1                       # 回退一步
```

迁移文件必须提交。

`f42a9c7e1d30` 是开发期 schema-only cutover：按外键顺序清空不兼容的 Project 执行、
Activity、Notification、Fork 与配置状态，随后删除 Workspace 兼容列、私有迁移表和
`workspaces` 表。downgrade 只恢复空的前序 schema shape，不恢复已删除的数据。

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
