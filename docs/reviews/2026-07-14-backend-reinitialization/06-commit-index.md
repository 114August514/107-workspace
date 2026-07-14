# 被审阅提交索引

本文按时间顺序列出 `origin/master..5d69a47` 的 17 个提交。文件数和行数是各提交
当时的 churn，不应直接相加后与最终 diff 对比，因为同一文件可能被多个提交修改。

## 1. 提交总表

| # | 提交 | 主题 | 文件与行数 | 阶段 |
| ---: | --- | --- | --- | --- |
| 1 | `d9a3fff` | `docs: define workspace backend architecture` | 1 file，`+796` | 架构规格 |
| 2 | `17bcf6c` | `docs: plan layered backend reinitialization` | 2 files，`+1,780/-5` | 架构规格 |
| 3 | `28fc895` | `refactor: archive runbox and reset repository layout` | 25 files，`+1,588/-193` | 仓库重置 |
| 4 | `409782b` | `feat: scaffold independent workspace backend` | 12 files，`+782` | 仓库重置 |
| 5 | `bdd5186` | `feat: define workspace domain policies` | 9 files，`+193` | 领域基础 |
| 6 | `e5056e7` | `feat: define backend port contracts` | 8 files，`+956` | 领域基础 |
| 7 | `a7828e8` | `feat: add workspace persistence schema` | 11 files，`+1,054` | 持久化 |
| 8 | `dfe72ba` | `feat: add repository unit of work` | 6 files，`+1,226/-10` | 持久化 |
| 9 | `9c98742` | `feat: add workspace membership APIs` | 16 files，`+1,016/-1` | 协作资源 |
| 10 | `f416583` | `feat: add projects and versioned datasets` | 20 files，`+1,106/-3` | 协作资源 |
| 11 | `bc945ea` | `feat: add run templates and preflight policy` | 10 files，`+954` | 模板与预检 |
| 12 | `dda4061` | `feat: add safe incremental project transfer` | 20 files，`+1,070/-6` | 项目传输 |
| 13 | `cc87aef` | `feat: add durable mock cluster adapter` | 6 files，`+719` | Mock 运行 |
| 14 | `a321a0b` | `feat: add run orchestration and reconciliation` | 10 files，`+1,611` | 运行编排 |
| 15 | `9be962a` | `feat: expose complete mock run workflow` | 17 files，`+1,281/-42` | 运行 API |
| 16 | `cf9fa4c` | `feat: add layered slurm and ssh adapters` | 25 files，`+2,593/-15` | Slurm/SSH |
| 17 | `5d69a47` | `docs: complete backend development and acceptance guide` | 15 files，`+2,041/-14` | 验收收尾 |

## 2. 逐提交审阅重点

### 1-2. `d9a3fff`, `17bcf6c`

先确认设计和计划是否准确表达需求。后续实现均以这里定义的依赖方向、非目标、
安全决策和 12 项验收标准为准。

### 3. `28fc895`

确认旧 RunBox 是移动和归档，而不是被活动后端继续导入；确认生成缓存已删除；
确认 `ref.md` 和 `foo.md` 只是设计输入。

### 4. `409782b`

确认 `backend/` 可以独立同步依赖、启动健康端点并运行 Ruff、Pyright 和 pytest；
确认配置默认值不会写出项目允许范围。

### 5-6. `bdd5186`, `e5056e7`

审阅领域模型、状态机、权限、路径值对象和 Protocol 端口。这里决定后续模块能否
解耦协作，应优先于数据库和 API 审阅。

### 7-8. `a7828e8`, `dfe72ba`

对照领域模型检查 12 张表、唯一约束、外键、索引和 migration downgrade；检查
Repository 是否始终限定 workspace scope，UoW 是否正确 commit/rollback。

### 9. `9c98742`

审阅可信身份头、工作区父子规则、owner/manager 权限、最终 owner 约束、成员管理
和归档后的行为。

### 10. `f416583`

审阅项目与数据集访问控制、不可变 DatasetVersion、内容寻址存储、上传下载和
归档语义。

### 11. `bc945ea`

审阅模板规格、环境和资源推断、preflight 错误是否可解释，以及路径与资源限制
是否在 submit 前完整执行。

### 12. `dda4061`

审阅 `.hpcignore`、目录剪枝、manifest、符号链接、允许根目录和增量 push/pull
语义。该提交建立了后续 SSH 传输需要遵守的合同。

### 13. `cc87aef`

审阅 Mock 状态文件的原子写入、损坏状态处理、时间推进、取消、日志 offset、结果
生成和跨 adapter 重建。

### 14. `a321a0b`

重点审阅运行 snapshot、事务外 submit、失败持久化、CAS、取消竞态、reconciler
错误隔离和产物只收集一次。这是运行一致性的核心提交。

### 15. `9be962a`

审阅 Run API、Problem Details、SSE offset、lifespan 中的 reconciler、Mock 重启和
HTTP 权限。确认 API 只是应用服务的适配层。

### 16. `cf9fa4c`

最高风险提交。逐一审阅 renderer、parser、command runner、Slurm adapter、SSH
transport、PAX tar pipeline、远程允许根目录和命令注入测试。

### 17. `5d69a47`

除了 README、smoke 和覆盖率测试，还修改了生产文件
`backend/src/workspace107/infrastructure/transfer/ssh.py`：缺失本地项目文件现在转为
`ResourceNotFound`，不再泄漏原生 `FileNotFoundError`。该变化需要独立审阅。

## 3. 常用审阅命令

查看完整提交序列：

```bash
git log --reverse --stat origin/master..5d69a47
```

查看单个提交：

```bash
git show --stat cf9fa4c
git show cf9fa4c -- backend/src/workspace107/infrastructure/cluster/slurm
```

按层比较最终结果：

```bash
git diff origin/master..5d69a47 -- backend/src/workspace107/domain
git diff origin/master..5d69a47 -- backend/src/workspace107/application
git diff origin/master..5d69a47 -- backend/src/workspace107/infrastructure
git diff origin/master..5d69a47 -- backend/src/workspace107/api
```

只看最终提交中的生产代码：

```bash
git show 5d69a47 -- backend/src
```

查看归档和延期范围：

```bash
git diff --summary origin/master..5d69a47 -- archive runbox runbox.egg-info
git diff origin/master..5d69a47 -- frontend docker deploy
```

## 4. 快照状态

该索引只描述 `origin/master..5d69a47`，不代表这些提交后来是否已经推送或合并。
快照采集时：

- `master` 相对 `origin/master` ahead 17、behind 0；
- 工作区干净；
- 未执行 push 或创建 PR；
- 本审阅包是快照之后新增的独立文档提交，不属于上述 17 个提交。
