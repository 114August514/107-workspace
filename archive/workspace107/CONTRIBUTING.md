# 贡献指南

新成员从这里开始。读完这一篇就可以提交第一个 PR。

完整命令和背景解释在 [`docs/development/git-workflow.md`](docs/development/git-workflow.md)。

一句话概括团队约定：

> **Issue 说明要做什么，分支隔离修改，Commit 记录过程，PR 完成评审，CI 保证基本质量，main 保存可信版本。**

---

## 一. 一次性准备

### 1.1 配置 Git 身份

```bash
git config --global user.name "你的名字"
git config --global user.email "你的 GitHub 邮箱"
```

确认配置：

```bash
git config --global --list
```

### 1.2 克隆仓库

```bash
git clone <仓库地址>
cd workspace107
git status
git remote -v
```

### 1.3 安装依赖

后端（需要 [uv](https://docs.astral.sh/uv/)）：

```bash
cd backend
uv sync --all-extras
uv run alembic upgrade head
```

前端（需要 Node 22+）：

```bash
cd frontend
npm ci
```

本地配置：

```bash
cp .env.example backend/.env
```

`backend/.env` 已被 `.gitignore` 排除，永远不要提交它。

### 1.4 启动

```bash
# 终端 1：后端，http://127.0.0.1:8000/docs
cd backend && uv run uvicorn workspace107.main:create_app --factory --reload

# 终端 2：前端，http://127.0.0.1:5173
cd frontend && npm run dev
```

---

## 二. 标准开发流程

```text
Issue → 创建分支 → 本地开发 → Commit → Push → Pull Request
     → Review + CI → Squash Merge → 删除远程分支 → 同步 main → 删除本地分支
```

### 2.1 领取 Issue

所有正式工作先建立 Issue，写清楚背景、目标、范围、验收条件和不做什么。
一个 Issue 控制在半天到三天内完成，过大的任务拆开。

### 2.2 从最新 main 创建分支

```bash
git checkout main
git pull --ff-only origin main
git checkout -b feat/123-create-workspace
```

分支命名统一为 `<类型>/<Issue编号>-<简短描述>`：

| 类型 | 用途 |
| :--- | :--- |
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `refactor` | 不改变行为的重构 |
| `test` | 测试 |
| `docs` | 文档 |
| `chore` | 工程配置、依赖、CI |

禁止直接在 `main` 上开发，也不要维护长期个人分支。

### 2.3 开发与提交

```bash
git status
git diff
git add backend/src/workspace107/application/workspace_service.py
git diff --staged
git commit -m "feat(workspace): 支持创建协作空间"
```

只 `add` 自己确认过的文件，不要习惯性 `git add .`。
Commit 格式和范围列表见 [`docs/development/commit-convention.md`](docs/development/commit-convention.md)。

### 2.4 提交前自检

```bash
./scripts/check.sh
```

它会依次执行后端 lint、格式检查、测试，前端 lint、类型检查、测试和构建，
以及接口契约与前端类型的一致性检查——和 CI 跑的是同一组命令。

### 2.5 推送并创建 PR

```bash
git push -u origin feat/123-create-workspace
```

PR 标题格式与 Commit 相同。描述按模板填写关联 Issue、修改内容、验证方式、
影响范围和截图。任务未完成但想提前同步设计时，直接开 Draft PR。

一个 PR 只解决一个主要问题，人工修改建议控制在 300~500 行以内。
生成的 `openapi.json`、`schema.d.ts` 和 lock 文件单独说明，不计入评审规模。

### 2.6 合并与清理

仓库只允许 **Squash and merge**，合并后自动删除远程分支。本地仍需手动清理：

```bash
git checkout main
git pull --ff-only origin main
git branch -D feat/123-create-workspace
git fetch --prune
```

---

## 三. 什么能提交，什么不能

### 应当提交

```text
uv.lock                       package-lock.json
数据库迁移文件                 .env.example
Dockerfile / compose           CI workflow
docs/api/openapi.json          frontend/src/api/schema.d.ts
.gitattributes / .editorconfig
```

后两个是生成物，但必须提交：改动在评审里看得见，新成员 clone 下来直接能编译。
改了后端 DTO 或路由之后跑一次：

```bash
./scripts/sync-api-contract.sh
```

**不要在前端手写接口类型。** 所有类型都从 `schema.d.ts` 派生，
这样后端改一个字段，前端受影响的地方会在类型检查时全部报出来，
而不是等到运行时。见
[ADR-0006](docs/decisions/0006-dependency-injection-and-api-contract.md)。

### 绝对不能提交

```text
.env、真实数据库密码、SLURM_JWT、GitHub Token、SSH 私钥、校园认证 Cookie
用户上传文件、用户数据集、模型权重、checkpoint
运行日志、Run 输出目录、数据库 dump
.venv/、node_modules/、dist/、各类缓存目录
```

**Slurm JWT 等价于密码**，只能通过环境变量注入。

不小心提交了密钥时，第一步永远是**立即轮换密钥**，然后通知维护者清理历史，
而不是先研究怎么改 Git 历史。详见
[`docs/development/troubleshooting-git.md`](docs/development/troubleshooting-git.md)。

### 大文件

107 Workspace 中的用户文件、训练数据、模型 checkpoint 和 Run 产物，
默认都不进入 Git 仓库或 Git LFS，它们属于算力平台存储。

确需版本化的少量二进制资源才使用 Git LFS，并且规则必须限定目录：

```bash
git lfs track "docs/demo/*.mp4"   # 可以
git lfs track "*.pt"              # 不可以
```

新增 LFS 规则要经过 PR 评审。

---

## 四. 评审

Reviewer 按这个顺序检查：

```text
1. 是否真正满足 Issue 的验收条件
2. 是否破坏现有行为
3. 模块边界是否正确
4. 是否有必要测试
5. 权限和输入校验是否完整
6. 是否泄露密钥或用户数据
7. 命名和可读性是否合理
```

不要在 Review 中只讨论格式而忽略业务正确性。详见
[`docs/development/code-review.md`](docs/development/code-review.md)。

---

## 五. 五条底线

```text
1. 不在 main 上开发
2. 开始工作和提交前都执行 git status
3. 只 add 自己确认过的文件
4. 一个 PR 只解决一个主要问题
5. 遇到冲突先停下来理解，不盲目复制命令
```
