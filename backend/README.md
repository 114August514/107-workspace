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
│   ├── run_snapshot.py   不可变执行事实（GR-009）
│   ├── secrets.py        环境变量表达式与 Secret 引用（GR-012）
│   ├── compute.py        算力方案、请求与调度解析
│   └── ports/            Scheduler / Storage / SecretVault / Repositories / Clock
├── application/      用例编排、权限校验、事务边界
│   ├── access.py         AccessGuard（GR-001 / GR-013）
│   ├── run_service.py    提交前检查、创建 Run、重跑、取消
│   └── run_lifecycle.py  状态同步与 Artifact 收集（GR-015）
├── infrastructure/   端口实现：SQLAlchemy 仓储、本地存储、Mock/Slurm 调度
├── api/              路由与 schema，不写业务规则
├── tools/            OpenAPI 导出、种子数据
└── main.py           唯一的装配点
```

## 依赖注入

具体实现只在**两个组合根**里被构造，别处一律拿协议：

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

这些约定由 `tests/unit/test_layering.py` 检查，违反了跑测试就红。
背景见 [ADR-0006](../docs/decisions/0006-dependency-injection-and-api-contract.md)。

## 安装与运行

```bash
uv sync --all-extras
uv run alembic upgrade head
uv run python -m workspace107.tools.seed
uv run uvicorn workspace107.main:create_app --factory --reload
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
| `WORKSPACE107_STORAGE_ROOT` | Project 文件、Run 目录、日志和 Artifact 的根目录 |
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

两者都只实现 `submit` / `poll` / `cancel`，没有「标记成功」的入口——
Run 状态只能由调度系统的轮询结果驱动（GR-015）。

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
uv run pytest                       # 全部
uv run pytest tests/unit            # 只跑单元测试
uv run pytest --cov                 # 带覆盖率
uv run ruff check . && uv run ruff format --check .
```

测试分层：

```text
tests/unit/         领域规则与不变量，不碰数据库
tests/integration/  端到端闭环，真实 SQLite + 真实子进程执行
tests/security/     GR-012 Secret 不落明文、GR-013 无发现权限即不存在
tests/contract/     API 契约与错误码映射
```

## 接口契约

改了 DTO 或路由之后必须重新生成契约和前端类型，否则 CI 的
`api-contract-check` 会失败：

```bash
../scripts/sync-api-contract.sh
```

它会依次导出 `docs/api/openapi.json` 和 `frontend/src/api/schema.d.ts`，
两个生成物都要提交。前端所有类型从后者派生，所以**后端改一个字段，
前端受影响的地方会在类型检查时全部报出来**。

写 DTO 时让契约说实话，生成的类型才有约束力：

- 是枚举就写成枚举（`status: RunStatus`），不要写 `str`
- 结构固定就定义模型，不要用 `dict[str, object]`
- 可以不传的字段写 `X | None = None`，不要用空字符串当默认值
- 新增的错误类型记得在 `api/routes/__init__.py` 的 `COMMON_ERRORS` 里体现
