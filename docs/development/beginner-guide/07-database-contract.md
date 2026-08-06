# 第七章：数据库与接口契约

数据库保存服务内部状态，API 契约规定前后端交换的数据。两者都会随功能演进，但修改方式不同：
数据库结构通过 Alembic 迁移，API 类型通过 OpenAPI 自动生成。本章给出日常开发所需的最小
流程。

## 7.1 领域模型不等于数据库表

`backend/src/workspace107/domain/` 中的模型表达业务含义；
`infrastructure/db/tables.py` 中以 `Row` 结尾的类描述数据库表；
`infrastructure/db/repositories.py` 在两者之间转换。例如 Application 使用 `Run`，Repository
才负责创建或读取 `RunRow`。不要把 SQLAlchemy 的 Row 对象传到路由或 Domain。

当前实现使用 SQLAlchemy 的异步 Engine 和 Session。默认本地数据库是 SQLite，部署可使用
PostgreSQL。`infrastructure/db/session.py` 会为 SQLite 开启外键检查，让本地更早发现悬空引用；
`expire_on_commit=False` 则允许事务提交后继续读取已经加载的对象属性。

几个基础概念足以开始开发：

| 概念 | 在项目中的作用 |
| --- | --- |
| 主键 | 唯一标识一行，如 `runs.id` |
| 外键 | 保证引用对象存在，如 `runs.project_id` 指向 Project |
| 唯一约束 | 防止重复数据，如同一 Workspace 内 Project 不能重名 |
| 索引 | 加速常用过滤和排序，如按 Workspace 或状态查 Run |
| 事务 | 一组操作整体提交；异常时整体回滚 |

应用层校验不能代替数据库约束。两个并发请求都可能在“先查是否存在”时得到否，随后同时插入；
唯一约束才是最后一道防线。`repositories.py` 的 `_flush()` 会把已知唯一约束冲突翻译为可理解
的 `ConflictError`，而不是把数据库异常直接暴露为 500。

Run Snapshot 是一个值得注意的例外：当前表以 JSON `payload` 保存完整执行事实，仓储端口
只有插入和读取。`RunRow` 另存 `compute_plan_id` 等需要稳定查询的字段。不要因为 JSON 修改
方便就更新旧 Snapshot；不可变性由 Domain 和 Repository API 共同保护。

## 7.2 Repository 与归属过滤

Application 通过 `domain/ports/repositories.py` 中的协议访问数据，具体 SQL 位于
`infrastructure/db/repositories.py`。一个最小查询大致如下：

```python
stmt = (
    select(RunRow)
    .where(RunRow.project_id == project_id)
    .order_by(RunRow.created_at.desc())
)
rows = (await session.execute(stmt)).scalars().all()
```

但多用户资源不能只写 `WHERE id = ?`。查询或调用前必须携带 Workspace/Project 归属上下文，
或由 `AccessGuard` 继续解析所属对象和 Membership。列表查询同样必须限制为用户可见的
Workspace。测试时要换成另一个用户并传入不属于他的 ID，仅使用自己的数据无法发现越权。

Session 通常由 `api/deps.py` 管理：请求成功 `commit`，异常 `rollback`。Repository 可以
`flush` 以尽早取得约束错误，但不应随意提交整个请求事务。需要并发控制时，沿用已有的行锁、
唯一约束或条件更新模式，不要凭“先查再改”假设请求不会同时发生。

## 7.3 Alembic 迁移

修改 `tables.py` 只会改变 Python 对未来表结构的理解，不会改变已经存在的数据库。Alembic 用
有顺序的迁移文件记录每次结构变化，文件位于 `backend/migrations/versions/`。

常规流程是：

```bash
# 1. 修改 infrastructure/db/tables.py 后，在 backend/ 中生成草稿
uv run alembic revision --autogenerate -m "add run priority"

# 2. 人工检查生成的 upgrade() 和 downgrade()

# 3. 在仓库根目录应用到最新版本
make migrate

# 4. 实际回退一步，再重新升级
make migrate-down
make migrate
```

自动生成只是草稿，必须检查列是否可空、默认值、外键、索引、约束名称，以及旧数据是否能转换。
新增非空列时尤其要考虑现有行。迁移的数据库地址来自 `WORKSPACE107_DATABASE_URL`，与应用共用
配置；执行前确认没有指向不应修改的数据库。

本项目规定迁移和认证授权相关代码不能在普通任务中直接改动，必须先提出并由维护者决定。
获得许可后也要提交迁移文件，并真实验证升级与回退。不要删除或改写已被共享环境使用的旧迁移，
应新增一条后续迁移。

## 7.4 从 FastAPI 到前端类型

接口契约的生成链如下：

```text
api/routes/ 路由 + api/schemas.py DTO
                    │ FastAPI 导出
                    ▼
          contracts/openapi.json
                    │ openapi-typescript
                    ▼
       frontend/src/api/schema.d.ts
```

`backend/src/workspace107/tools/export_openapi.py` 创建一个不连接数据库和调度系统的应用并调用
`app.openapi()`。`scripts/tasks/contract.py` 随后运行 `openapi-typescript` 生成前端声明。统一命令
是：

```bash
make contract        # 更新两个生成文件
make contract-check  # 检查已提交文件是否与后端一致
```

Windows 没有 Make 时使用相同任务实现：

```powershell
uv run --no-project python scripts/workspace.py contract sync
uv run --no-project python scripts/workspace.py contract check
```

`contracts/openapi.json` 和 `frontend/src/api/schema.d.ts` 都不得手工编辑。修改路由、请求/响应
Schema、状态码、媒体类型或错误响应后，运行 `make contract` 并提交两个生成文件。`make check`
会在临时目录重新生成并比较，遗漏更新会直接失败。

## 7.5 让契约准确表达接口

以 `api/schemas.py` 中的 Run 为例：`RunDraftIn.project_version_id` 是可省略字段，所以写成
`str | None = None`；`RunOut.status` 使用 `RunStatus` 枚举；已解析调度配置使用
`ResolvedSchedulerOut`，而不是 `dict[str, object]`。这样生成的前端类型才能说明字段是否必需、
允许哪些状态、嵌套对象有哪些属性。

响应的媒体类型也属于契约。Artifact 下载路由明确声明 `application/octet-stream` 和 binary
Schema，否则 FastAPI 默认可能把它描述为 JSON，前端生成类型就会错误。类似地，新异常若是
所有路由都可能返回，应检查 `api/routes/__init__.py` 的 `COMMON_ERRORS` 是否需要补充。

一次 API 字段修改的检查清单如下：

1. 修改后端 Schema、Presenter 和对应测试，不先改生成文件。
2. 判断这是兼容新增还是会破坏现有调用方的删除、改名或类型变化。
3. 运行 `make contract`，阅读 OpenAPI 和 TypeScript 的差异。
4. 修复前端类型检查指出的调用位置，不用类型断言掩盖错误。
5. 运行 `make check`，再通过 `/docs` 或实际页面验证成功与错误响应。

数据库迁移与 API 契约经常同时变化，但不要把它们混成一步：表中存在某列不代表必须原样暴露；
API 新增字段也可能来自计算结果而无需改表。先确定业务语义，再分别修改持久化边界和 HTTP 边界。
