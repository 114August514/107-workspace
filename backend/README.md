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
├── application/      API 用例与独立 Worker 执行编排
│   ├── access.py         AccessGuard（GR-101 / GR-102 / GR-103）
│   ├── run_service.py    preflight、创建 Run 与 execution-context revalidation
│   └── run_worker.py     持久 intent、workspace、Scheduler、Artifact 推进
├── infrastructure/   SQLAlchemy、Git、POSIX workspace、Mock/Slurm adapter
├── api/              路由与 schema，不写业务规则
├── tools/            OpenAPI、seed 与隔离 smoke database
├── main.py           HTTP API composition root
└── worker.py         single-active independent Worker composition root
```

## 依赖注入

具体实现只在对应进程的 composition root 中构造，其他模块只拿协议：

```text
domain/ports/     用 Protocol 描述「需要什么能力」
application/      构造函数注入，只认这些协议
infrastructure/   实现协议
main.py           API：数据库、local storage、Git project content、clock（无 Scheduler/credential）
worker.py         Worker：execution store/context、Git exporter、Run workspace、Scheduler
api/deps.py       请求级仓储、Secret vault 和用例服务
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

API 与 Worker 是两个明确入口。Scheduler 配置和 credential 只属于 Worker；API 不 submit、
poll 或推进 execution intent。依赖方向与里程碑边界以 ADR-0004 和产品设计为准。

## 安装与运行

```bash
uv sync --all-extras
uv run alembic upgrade head
uv run python -m workspace107.tools.seed
uv run uvicorn workspace107.main:create_app --factory --reload
```

独立 Worker 必须使用 PostgreSQL；在另一个终端以同一数据库/storage 配置运行：

```bash
uv run python -m workspace107.worker
```

`seed` 不带参数时只幂等创建本地开发 Compute Plans，不创建 Environment 或 Shared
Resource。显式演示 bootstrap 使用：

```bash
uv run python -m workspace107.tools.seed --demo
uv run python -m workspace107.tools.seed --demo --platform-owner-username <username>
```

Owner 选择顺序是 CLI、`WORKSPACE107_DEMO_PLATFORM_OWNER_USERNAME`、`student`，且只在
`grp_platform_assets` 首次不存在时生效。User Group 已存在时不会创建新配置的 User，也
不会改回或协调已转让的 Owner。演示 Project 使用 `grp_demo` 自己的 Environment；它与
`grp_platform_assets` 持有的两条平台演示 Environment 是不同资产。这不是 production
provisioning 接口。

接口文档：<http://127.0.0.1:8000/docs>

## 配置

全部通过环境变量注入，变量清单见仓库根目录的 `.env.example`。
本地把它复制成 `backend/.env` 即可：

```bash
cp ../.env.example .env
```

关键边界：

| 变量 | 进程 | 说明 |
| :--- | :--- | :--- |
| `WORKSPACE107_DATABASE_URL` | API + Worker | API 本地可用 SQLite；独立 Worker 必须 PostgreSQL |
| `WORKSPACE107_STORAGE_ROOT` | API + Worker | 两者看到的 canonical content root |
| `WORKSPACE107_STORAGE_GID` | API + Worker | canonical root GID；两进程都必须加入 |
| `WORKSPACE107_AUTH_MODE` | API | `dev` 用 `X-User` 请求头识别用户 |
| `WORKSPACE107_SHARED_GID` | Worker | local Run-tree sharing；当前必须等于 storage GID |
| `WORKSPACE107_SCHEDULER` | Worker | 当前仅 local/test `mock`；`slurm` 启动会 fail-closed |
| `WORKSPACE107_SLURM_*` | Worker only | fixture-backed adapter contract 与 secret；禁止注入 API |

## 开发模式下的身份

`WORKSPACE107_AUTH_MODE=dev` 时用 `X-User` 请求头识别用户。首次出现只建立 User 身份，
不创建额外 ownership 容器：

```bash
curl -H 'X-User: student' http://127.0.0.1:8000/api/v1/me
curl -X POST -H 'X-User: student' -H 'Content-Type: application/json' \
  -d '{"name":"计算物理课题组","description":""}' \
  http://127.0.0.1:8000/api/v1/user-groups
```

接入学校统一身份认证后只需替换 `api/deps.py` 中的 `get_current_user`。

## 调度适配器

| 适配器 | 行为 |
| :--- | :--- |
| `mock` | 在 Worker 主机以子进程真实执行；只允许 local/test，不是沙箱 |
| `slurm` | adapter 覆盖单目标 submit/find/poll/cancel，但 Worker 当前拒绝启动 |

当前全局 `shared_gid` 只能证明 compute identity 可访问一个 Run tree，不能阻止它访问同组的
其他 Run。真实 Slurm/native 执行因此在 `Settings.ensure_worker_configuration()` 机械 fail-closed；
必须先实现并验证 per-job identity、per-Run group/ACL 或 mount isolation 中的一种明确 contract。
稳定完整 correlation 仍用于 adapter 的 ambiguous submit reconcile；查询不完整或多匹配时停止。
Slurm credential 只从 Worker 环境注入；issuer、TTL、renewal、revocation 和 restart lifecycle
未经目标 107 验收前没有默认 policy。

Mock 会把渲染脚本放在对应 Run workspace；它只证明本地闭环，不证明真实 mount/profile。

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
