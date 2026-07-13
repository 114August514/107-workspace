好的，我们重新按照目前确定的原则初始化：

目标：

* ✅ 后端优先开发
* ✅ Python + FastAPI
* ✅ uv 管理依赖
* ✅ 前后端分离
* ✅ Docker 后续加入，不现在绑定
* ✅ 未来方便接真实 Slurm / SCOW
* ✅ 工程规范（Google Style + Ruff + Pyright）
* ✅ 不过度 DDD

最终采用：

```text
107-workspace
│
├── backend/        # 现在主要开发
├── frontend/       # 预留
├── docker/         # 预留
├── deploy/         # 预留
├── docs/           # 设计文档
├── scripts/        # 工具脚本
└── README.md
```

---

# Step 0：创建仓库

```bash
mkdir 107-workspace

cd 107-workspace

git init
```

初始化：

```bash
touch README.md
touch .gitignore
```

---

# Step 1：创建整体目录

```bash
mkdir backend frontend docker deploy docs scripts
```

现在：

```text
107-workspace/

├── backend/
├── frontend/
├── docker/
├── deploy/
├── docs/
├── scripts/
├── README.md
└── .gitignore
```

---

# Step 2：初始化 Python 后端

进入：

```bash
cd backend
```

使用 uv：

```bash
uv init
```

生成：

```text
backend/

├── pyproject.toml
├── README.md
└── .python-version
```

指定 Python：

```bash
uv python pin 3.12
```

检查：

```bash
cat .python-version
```

应该：

```text
3.12
```

---

# Step 3：添加基础依赖

## Web 框架

```bash
uv add fastapi
```

运行服务器：

```bash
uv add "uvicorn[standard]"
```

---

## 数据库

```bash
uv add sqlalchemy
uv add alembic
```

---

## 数据校验和配置

```bash
uv add pydantic-settings
```

---

## 测试

开发依赖：

```bash
uv add --dev pytest
```

---

## 工程工具

```bash
uv add --dev ruff
uv add --dev pyright
```

最后：

```bash
uv sync
```

生成：

```text
uv.lock
```

---

# Step 4：配置 pyproject.toml

打开：

```text
backend/pyproject.toml
```

加入：

```toml
[tool.ruff]
line-length = 88
target-version = "py312"


[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "strict"


[tool.pytest.ini_options]
testpaths = [
    "tests"
]
```

---

# Step 5：创建后端目录结构

进入 backend：

```bash
mkdir -p app
```

创建：

```bash
mkdir -p app/api
mkdir -p app/core
mkdir -p app/models
mkdir -p app/schemas
mkdir -p app/services
mkdir -p app/repositories
mkdir -p app/adapters/cluster
mkdir -p app/adapters/storage
mkdir -p app/workers
mkdir -p app/utils
mkdir -p tests
mkdir -p migrations
```

最终：

```text
backend/

├── app/
│
│   ├── api/
│   │
│   ├── core/
│   │
│   ├── models/
│   │
│   ├── schemas/
│   │
│   ├── services/
│   │
│   ├── repositories/
│   │
│   ├── adapters/
│   │   ├── cluster/
│   │   └── storage/
│   │
│   ├── workers/
│   │
│   ├── utils/
│   │
│   └── main.py
│
├── tests/
│
├── migrations/
│
├── pyproject.toml
└── uv.lock
```

---

# Step 6：创建第一个 FastAPI 服务

创建：

```bash
touch app/main.py
```

内容：

```python
from fastapi import FastAPI


app = FastAPI(
    title="107 Workspace API",
    version="0.1.0",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint.

    Returns:
        Service status.
    """
    return {
        "status": "ok",
    }
```

---

# Step 7：运行后端

注意现在不用 activate venv。

直接：

```bash
uv run uvicorn app.main:app --reload
```

看到：

```text
Uvicorn running on http://127.0.0.1:8000
```

访问：

```text
http://127.0.0.1:8000/docs
```

应该看到 Swagger。

这就是未来前端调用入口。

---

# Step 8：配置 gitignore

根目录：

```text
.gitignore
```

加入：

```gitignore
# Python
__pycache__/
*.pyc

# Virtual env
.venv/

# Testing
.pytest_cache/

# Ruff
.ruff_cache/

# IDE
.vscode/
.idea/

# Environment
.env

# Frontend
node_modules/

# OS
.DS_Store
```

---

# Step 9：初始化 README

根 README：

```markdown
# 107 Workspace

A collaborative computing workspace for undergraduate computing platform.

## Structure

- backend: FastAPI backend
- frontend: Web client
- docker: containerization
- deploy: deployment configuration
- docs: design documents

```

---

# Step 10：创建 docs（建议马上做）

不要等。

创建：

```text
docs/

├── architecture.md
├── api.md
├── database.md
└── development.md
```

现在先写：

## architecture.md

记录：

```markdown
# Architecture

Frontend
    |
    | REST API
    |
FastAPI

    |
    |
Services

    |
    +-- Repository
    |
    +-- Cluster Adapter
    |
    +-- Storage Adapter
```

以后防止自己忘。

---

# Step 11：第一阶段不要创建的东西

暂时不要：

```
docker-compose.yml
Dockerfile
Redis
Celery
PostgreSQL
React
登录系统
真实 Slurm
```

原因：

现在目标不是部署，而是验证核心设计。

---

# Step 12：第一阶段开发顺序

初始化完成后：

## M0：健康检查

完成：

```
GET /health
```

---

## M1：领域模型

先设计：

```
User

Workspace

WorkspaceMember

Project

Dataset

RunTemplate

Run

Artifact
```

不要急着写接口。

---

## M2：数据库

加入：

```
SQLAlchemy
Alembic
SQLite
```

实现：

```
创建 Workspace
查询 Workspace
```

---

## M3：业务层

写：

```
WorkspaceService

ProjectService

RunService
```

---

## M4：Mock Slurm

实现：

```python
class ClusterAdapter:
    submit()
    status()
    cancel()
```

先：

```
MockClusterAdapter
```

---

## M5：跑通核心闭环

最终：

```
创建空间
 ↓
创建项目
 ↓
创建运行模板
 ↓
提交 Run
 ↓
Mock Slurm
 ↓
状态变化
 ↓
查看日志
 ↓
获取结果
```

---

# 最终初始化后的状态应该是：

```text
107-workspace

├── backend
│   ├── FastAPI
│   ├── uv
│   ├── SQLAlchemy
│   ├── Ruff
│   ├── Pyright
│   └── pytest
│
├── frontend
│   └── empty
│
├── docker
│   └── empty
│
├── deploy
│   └── empty
│
├── docs
│   └── architecture.md
│
└── README.md
```

然后进入真正开发。

---

下一步我建议不要直接写 Workspace CRUD，而是先设计 **107 Workspace 的数据库模型（User / Workspace / Project / Dataset / Run 的关系）**。因为这个项目后面所有功能都会围绕这些实体展开，模型设计错了后面返工最大。
