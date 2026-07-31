# 重构：transfer → execution_data

- 状态：已放弃
- 认领：（填你的名字）
- 上下文：backend/infrastructure
- 开始：2026-07-27（补记）

> ⚠️ **这份是事后补记，意图是从 `git diff` 反推的，不是做这件事的人写的。**
> 反推的意图可能是错的——请本人核对一遍，尤其是「意图」和「验收」两节。
>
> 补记的起因：接手时跑 `make test` 发现红的，花了十几分钟才判断出
> 「这是在途重构」而不是「主干坏了」。如果开工时就有这份记录，三十秒就够了。

## 结束记录

- 结束：2026-08-01
- 结果：未完成代码已从工作区移除
- 原因：仓库将迁入 `workspace107` 的已验证实现；继续完成这条新旧并存且仍为红态的
  重构不会形成可复用的迁移成果
- 保留：重构前的已提交实现由 tag
  `archive/pre-workspace107-migration-2026-08-01` 固定

## 意图

把 `transfer` 这一层重构成 `execution_data`。目前**新旧并存**，还没删旧的。

## 预期改动

已跟踪、已改动（7 个文件，+266 / −68）：

- `backend/src/workspace107/api/dependencies.py`
- `backend/src/workspace107/application/transfers.py`
- `backend/src/workspace107/main.py`
- `backend/tests/integration/api/test_project_transfer.py`
- `backend/tests/unit/api/test_errors_and_dependencies.py`
- `backend/tests/unit/test_runtime_wiring.py`
- `.gitignore`

新增、尚未跟踪：

- `backend/src/workspace107/infrastructure/execution_data/`
- `backend/tests/contract/execution_data/`

旧的还在，**尚未删除**：

- `backend/src/workspace107/...transfer...`
- `backend/tests/contract/transfer/`

## 当前状态：红的

```
make lint   ✗ 2 个 SIM105，两处都在**新代码**里（不是既存问题）
              src/workspace107/infrastructure/execution_data/local.py:66
              tests/contract/execution_data/test_ssh.py:100
              → try/except FileExistsError/pass 应改成 contextlib.suppress

make test   361 passed / 11 failed / 1 skipped
```

11 个失败分两类：

| 位置 | 数量 | 备注 |
|---|---|---|
| `tests/integration/api/` | 10 | 多数挂在 `run_support.py:123` 的断言上 |
| `tests/unit/domain/test_models.py` | 1 | `assert isinstance(FakeCluster(), ClusterPort)` 失败——像是 Port 协议在重构中变了形状 |

### 已经用独立 worktree 在 HEAD 上实测出基线

| | lint | 测试 |
|---|---|---|
| **HEAD（已提交）** | ✅ 全过 | **1 failed** / 350 passed / 1 skipped |
| **工作区（本次重构）** | ✗ 2 errors | **11 failed** / 361 passed / 1 skipped |

所以分得很干净：

- **既存问题（1 个，与本次重构无关）**
  `tests/unit/domain/test_models.py::test_runtime_port_contracts_accept_structural_implementations`
  —— `assert isinstance(FakeCluster(), ClusterPort)` 失败。主干上就是红的。
  **应该单独开一个 issue 修，不要混进这次重构的提交。**

- **本次重构引入（10 个失败 + 2 个 lint）**
  10 个全在 `tests/integration/api/`，多数挂在 `run_support.py:123` 的断言上；
  2 个 lint 都在新写的 `execution_data/` 里。
  本次重构也新增了 11 个测试（350 → 361 passed）。

**❓ 仍需本人确认**：那 10 个 integration 失败，是"重构还没做完，预期内"，
还是"改坏了"？

## 已经顺手做掉的

`tests/contract/execution_data/` 和 `tests/contract/transfer/` 里有同名的
`test_local.py` / `test_ssh.py`，两个目录都缺 `__init__.py`，导致 pytest
**模块名冲突、全量测试直接收集失败**（单独跑某个文件反而是通过的）。

已补上两个空 `__init__.py`，与 `cluster/`、`api/`、`workers/`、`security/`
的现有约定一致。补完后收集正常。

**这个冲突就是这次重构造成的**（新目录复用了旧目录的文件名），所以这两个文件
属于本次重构的一部分，可以直接收进同一个提交。

同名文件里还有一处**潜在的同类问题**：
`tests/integration/api/test_runs.py` 与 `tests/unit/application/test_runs.py`
也同名，目前没撞（前者所在目录有 `__init__.py`）。哪天有人调整 `__init__.py`
就会以同样的方式炸。根治办法是统一约定，而不是逐个补。

## 仓外副作用

无。（本次重构只动代码和测试，没跑迁移、没部署、没建外部资源。）

## 回退方式

尚未提交，`git checkout .` + 删掉未跟踪的新目录即可。
一旦提交，用 `git revert <commit>`。

## 验收

```
make check   全绿
```

补充两条（❓待本人确认）：

- 旧的 `transfer` 层是这次一并删掉，还是留到下一次？
- `ClusterPort` 的协议形状变了的话，`docs/` 里有没有对应的契约/设计要跟着改？

## 禁区

- 不动 `frontend/`（还没开始写）
- 不动 `alembic` 迁移（本次不涉及 schema）
- 不引入新依赖
