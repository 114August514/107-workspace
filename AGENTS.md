# 107 Workspace

面向本科生的算力平台：把 Slurm 的提交-排队-取结果流程，变成 Workspace / Project /
Run 的可复现工作流。

> **这份是宪法：只放不会过期的约束和指针。**
> 已经有专门文档的东西**一律不在这里重复**，重复的两份一定会有一份过期。

| 想知道 | 看 |
| --- | --- |
| 产品能力、**领域语言与规则** | `docs/product/design.md`（现行、已确认）——**术语以它 §3.1 为准** |
| 分支 / 提交 / PR / Milestone / 标签 / LFS | `docs/contributing/git-workflow.md` |
| 在途工作、谁在做什么 | `docs/journal/` + `make journal` |
| 为什么这么设计 | `docs/decisions/` |
| 容器部署入口与生产边界 | `deploy/README.md` + `docs/operations/deployment.md` |
| 前后端 API 机器契约 | `contracts/README.md` + `make contract` |

`archive/`、`docs/archive/` 和 `docs/references/` 保存历史实现、过程记录与输入材料，
不是活动规范。与它们冲突时以 `docs/product/design.md` 为准。

## 验证

提交前必须跑：

```bash
make check          # fmt-check + lint + typecheck + test + build + contract
```

Windows 没有 Make 时运行同一个实现：

```powershell
uv run --no-project python scripts/workspace.py check
```

**不要另外发明检查链**，也不要把直接调用 `pytest` / `pnpm` 的临时命令写进 CI——
那样 CI 和本地会分叉。声称"做完了"之前跑统一入口，并记录实际结果。

```bash
make dev            # 起后端
make migrate        # alembic 升到最新
make migrate-down   # 回滚一步（合并前必须实际验证过）
make coverage       # 带 90% 门槛
make journal        # 有没有在途工作、孤儿锁
make doctor         # 工程基线还缺什么
```

任务逻辑集中在 `scripts/workspace.py` 与 `scripts/tasks/`；`Makefile` 只负责转发。
平台专属引导脚本只放在 `scripts/platform/` 的对应目录。

## 目录

```text
backend/src/workspace107/
├── api/              # 路由与依赖注入 —— 只做协议转换，不写业务判断
├── application/      # 用例编排、事务边界
├── domain/           # 业务规则与模型 —— **不 import 任何 IO**
└── infrastructure/   # db / scheduler / storage 等外部依赖
backend/tests/        # unit / integration / contract / security
frontend/             # React + TypeScript 控制台
contracts/            # 跨组件机器契约；生成物不得手改
deploy/               # 可执行部署编排；服务镜像构建文件仍由服务目录维护
docs/decisions/       # ADR
docs/journal/         # 在途工作
```

**领域层不依赖基础设施层**，依赖方向永远朝内。做到这一条，业务规则才能用
毫秒级的纯单元测试密集覆盖。时钟和随机数也算 IO，当参数传进去。

## 命名

**以 `docs/product/design.md` §3.1 的术语表为唯一事实源**：User / Workspace /
Membership / Project / Project Version / Run Configuration / Run Snapshot /
Environment / Shared Resource / Content Version / Input Binding /
Compute Plan / Resource Entitlement …

代码标识符、数据库列、接口字段、日志字段全用同一个词。
**需要新概念时，先往 `docs/product/design.md` §3.1 加一行，再写代码。**

特别注意几组**容易混**的：

- `Run Configuration`（可编辑、可复用的方案）≠ `Run Snapshot`（创建后不可变的执行事实）
- `Environment`（决定代码在什么基础上跑）≠ `Shared Resource`（决定 Run 能读什么内容）
- `Entitlement Request`（申请记录）≠ `Resource Entitlement`（审批通过后的有效资格）

## 不变量

`docs/product/design.md` §3.3 的 Active GR 和 §3.1 的领域约束是本项目的不变量，
其中最硬的几条：

- **Run Snapshot 创建后不得修改**；执行时不得重新读取当前 Run Configuration
- **Run Snapshot / 日志 / 页面不得出现 Secret 明文**，只固定引用表达式
- Workspace 只能使用其 Resource Entitlement 允许的 Compute Plan
- 通过 Input Binding 提供的内容**只读**
- Project Version、Environment Version、Shared Resource Version、Profile Version
  **发布后不得原地修改**

**数据库约束是最后一道防线**，不要因为应用层已经校验过就省掉它。

## 禁止

- 不许改 `migrations/`、认证授权相关代码 —— 先提出来让人决定
- 不许新增依赖 —— 先说明现有的为什么不够
- 不许 skip / 注释掉 / 放宽失败的测试。测试红了就是代码错了
- 不许写只调用不断言的测试，或 mock 掉一切然后断言 mock 被调用了
- 不许硬编码配置（路径、地址、密钥），从 `WORKSPACE107_*` 环境变量读
- 不许在 `domain/` 里 import 数据库、HTTP、文件、时钟、随机数
- 不许把资源查询写成 `WHERE id = ?` —— **必须带归属过滤**（见下）

## 三条顺序不能反

1. **先搜再写** —— 仓库里已经有了吗？标准库有吗？已装的依赖有吗？
2. **先写测试再写实现**，而且要**亲眼看到它红**
3. **先在 `docs/journal/` 写意图再动手** —— 会话会死，写完意图那一刻才是可恢复的

## 这个项目特别容易错的三处

**① 越权。** 平台是多用户多 Workspace 的，`WHERE id = ?` 这种查询在功能测试里
完全正常（你用自己的账号点，看到的都是自己的数据），只有**换个账号带别人的 ID**
才会暴露。过滤必须落到数据访问层，并且写进方法签名让"忘了传"编译不过。
每个涉及资源的接口都要有一条「用别人的 ID → 403/404」的测试。

**② 不可变性。** Snapshot / Version 类对象一旦创建就不能改。写更新逻辑前先问：
这个对象是不是快照？是的话就该创建新的，而不是改旧的。

**③ 日常跑的是 mock。** `WORKSPACE107_SCHEDULER=mock` 会通过宿主机 shell 真实
执行用户命令，但没有真实 Git、Shared FS、独立 Worker 或 Apptainer。Slurm REST
适配器存在但尚未在 107 集群验证；本地闭环不等于现行 M1 已完成。

## 汇报

完成时说清六件事：做了什么 / **没做什么** / 怎么验证的（贴 `make check` 输出）/
**哪里不确定**（写满三条）/ **故意没处理的** / 碰了哪些文件（`git diff --stat`）。

不要用"应该没问题""看起来是对的"收尾。要么验证过并给出证据，要么明说没验证。
