# 测试与验收证据

本文记录 2026-07-14 对被审阅 HEAD `5d69a47` 执行的质量门和设计规格第 19 节
验收标准。结果来自实际命令输出，不包含本次新增审阅文档。

## 1. 总体结果

| 检查 | 结果 |
| --- | --- |
| `uv sync --all-extras` | 解析 44 个包，检查 43 个包，退出 0 |
| Alembic `upgrade -> downgrade -> upgrade` | 临时 SQLite 三步均退出 0 |
| 全量 pytest + branch coverage | `292 passed, 1 skipped` |
| 总分支覆盖率 | `90.38%`，通过 90% 门槛 |
| 聚焦验收测试 | `124 passed` |
| `ruff format --check .` | 126 个文件已格式化 |
| `ruff check .` | 无问题 |
| 严格 Pyright | 0 errors，0 warnings |
| `uv lock --check` | 退出 0 |
| `bash -n scripts/smoke-backend.sh` | 退出 0 |
| 真实 Uvicorn HTTP smoke | `1 passed` |

普通 pytest 中的一个 skip 是预期行为：live smoke 需要一个已经启动的 TCP 服务，
因此普通测试只收集并跳过它；随后由 `scripts/smoke-backend.sh` 单独启动服务并验证。

## 2. 测试结构

`backend/tests/` 共 50 个版本化测试相关文件，其中有 42 个 `test_*.py` 模块：

| 类型 | 测试模块数 | 主要目的 |
| --- | ---: | --- |
| Contract | 4 | Mock/Slurm 集群合同和 Local/SSH 传输合同 |
| Integration | 17 | API、数据库、迁移、Repository、UoW 和 reconciler |
| Security | 1 | 命令注入、错误清理、tar 选项终止 |
| Smoke | 1 | 真实 TCP 上的完整 HTTP 工作流 |
| Unit | 18 | Domain、Application、Infrastructure 和运行时组合 |
| 根级测试 | 1 | 健康检查 |

测试入口：

- [../../../backend/tests/unit/](../../../backend/tests/unit/)
- [../../../backend/tests/integration/](../../../backend/tests/integration/)
- [../../../backend/tests/contract/](../../../backend/tests/contract/)
- [../../../backend/tests/security/](../../../backend/tests/security/)
- [../../../backend/tests/smoke/](../../../backend/tests/smoke/)

## 3. 十二项验收映射

| # | 验收标准 | 直接证据 | 状态 |
| ---: | --- | --- | --- |
| 1 | 后端可以只用自己的项目文件安装 | `uv sync --all-extras` 和 `uv lock --check`；无外部 path dependency | 通过 |
| 2 | 活动后端不导入三个参考项目 | 源码、`pyproject.toml`、lock 的 `rg` 扫描无匹配 | 通过 |
| 3 | RunBox 归档且无生成缓存 | `archive/runbox-v0/ARCHIVE.md` 存在；`find` 未发现 pycache、pyc、pytest cache、egg-info | 通过 |
| 4 | 迁移创建全部模型并执行约束 | 三段迁移成功；schema、唯一约束和 SQLite 外键测试通过 | 通过 |
| 5 | 客户端可创建协作资源 | live smoke 创建用户、课程工作区、成员、项目、数据集版本和模板 | 通过 |
| 6 | 客户端可完成 Mock 运行 | live smoke 观察 queued/running/succeeded，读取日志并校验产物 SHA-256 | 通过 |
| 7 | 失败和安全边界有测试 | 失败、取消、非法转换、越权、归档、路径穿越和命令注入测试通过 | 通过 |
| 8 | Mock 外部状态跨应用重建 | `test_mock_run_survives_application_reconstruction` 通过 | 通过 |
| 9 | Slurm 实现通过公共合同 | fake command runner 下 Slurm contract 和边界测试通过 | 通过 |
| 10 | Local/SSH 传输通过合同 | 扫描、本地传输、SSH 命令和 tar pipeline 测试通过 | 通过 |
| 11 | 全部质量门通过 | pytest、coverage、migration、Ruff、Pyright、lock 和 smoke 均退出 0 | 通过 |
| 12 | 文档覆盖架构和开发流程 | 根 README、后端 README、设计规格和实施计划均存在 | 通过 |

聚焦验收命令覆盖第 4、7、8、9、10 项，共 `124 passed`：

```bash
cd backend
uv run pytest \
  tests/integration/db \
  tests/security \
  tests/unit/application/test_preflight.py \
  tests/unit/application/test_runs.py \
  tests/unit/domain/test_state_machine.py \
  tests/integration/api/test_runs.py \
  tests/integration/api/test_run_logs.py \
  tests/integration/api/test_mock_restart.py \
  tests/contract/cluster/test_slurm.py \
  tests/contract/transfer/test_local.py \
  tests/contract/transfer/test_ssh.py -q
```

## 4. 完整复验命令

在仓库根目录执行依赖同步：

```bash
cd backend
uv sync --all-extras
uv lock --check
```

使用一次性 SQLite 数据库验证迁移：

```bash
export WORKSPACE107_DATABASE_URL=sqlite+aiosqlite:////tmp/workspace107-review.db
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

该数据库必须是可丢弃文件；`downgrade base` 会删除后端 schema。

运行完整质量门：

```bash
uv run pytest \
  --cov=workspace107 \
  --cov-report=term-missing \
  --cov-fail-under=90
uv run ruff format --check .
uv run ruff check .
uv run pyright
cd ..
bash -n scripts/smoke-backend.sh
./scripts/smoke-backend.sh
```

## 5. Live smoke 覆盖范围

[../../../scripts/smoke-backend.sh](../../../scripts/smoke-backend.sh) 会创建临时数据库、
存储、传输和 Mock 根目录，然后：

1. 应用 Alembic migration；
2. 启动监听 `127.0.0.1` 的真实 Uvicorn；
3. 等待 `/health` 可用；
4. 运行 [test_http_workflow.py](../../../backend/tests/smoke/test_http_workflow.py)；
5. 验证完整资源创建、项目 push、preflight 和 run submit；
6. 轮询 queued、running、succeeded；
7. 读取日志并下载结果；
8. 对下载内容重新计算 SHA-256，与 artifact metadata 对比；
9. 退出时终止服务并删除临时目录。

## 6. 仍未覆盖的环境证据

当前验收不包含真实 Slurm 控制器、真实 SSH host key、集群账号、配额、共享文件系统
或 SCOW 会话。Slurm/SSH 已有 contract、fake runner、subprocess 和安全边界测试，
但部署前仍需要在目标集群执行现场验收。这是已知范围边界，不应由本地 smoke 的
通过结果替代。
