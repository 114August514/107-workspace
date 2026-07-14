# 107 RunBox

一个面向初学者的**本地 Web GUI**,把在 HPC 集群上跑作业的繁琐流程变成浏览器里的几个按钮。

RunBox 是套在 [`hpc-helper`](../../hpc-helper) 引擎之上的一层薄 FastAPI 应用:它不重新实现集群逻辑,只是把引擎的能力用一个清爽的四步工作流暴露出来。

```
① 申请节点  →  ② 同步代码  →  ③ 运行脚本  →  ④ 取回结果
  (GPU)          (rsync)         (sbatch/srun)     (download)
```

---

## 它解决什么问题

在集群上跑一次实验,通常要手动串起 6 步:`up → push → run → logs → pull → down`——申请节点、上传代码、提交作业、看日志、拉结果、释放节点。命令多、容易记错、日志要来回 SSH 看。

RunBox 把这套循环变成一个网页:左侧是导航,中间是按步骤排列的卡片,运行日志实时流式显示在内置终端里。

---

## 架构

```
浏览器 (runbox/static/index.html — 单页应用, SSE 实时日志)
   │  REST + Server-Sent Events
   ▼
runbox/app.py      FastAPI 路由层,与引擎函数 1:1 映射
runbox/engine.py   把阻塞式引擎调用丢到 worker 线程(anyio.to_thread)
   │
   ▼
hpc_helper.api     纯函数引擎:load_config / up / down / push / start_run / pull …
                   失败抛 EngineError 子类(ConfigError/AuthError/AllocError/SyncError)
```

**两种运行位置(自动检测):**

| 模式 | 何时使用 | 如何执行命令 |
|------|----------|--------------|
| `local` | 跑在集群登录节点上(检测到本机有 `squeue`/`sbatch`) | 直接 `subprocess` 本机执行,不走 SSH |
| `ssh`   | 跑在学生自己的笔记本上 | 通过 SSH 驱动集群 |

检测逻辑在 `runbox/app.py`:发现本机有 `squeue` 且 `sbatch` 就切到 `local`。

---

## 安装

需要 Python ≥ 3.10,以及可用的 `hpc_helper` 引擎(以 editable 方式安装)。

```bash
cd ~/projects/p107
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e ~/hpc-helper   # 引擎,RunBox 依赖它但不在本包声明
```

---

## 启动

```bash
runbox                      # 控制台脚本入口
# 或
.venv/bin/uvicorn runbox.app:app --host 0.0.0.0 --port 8760
```

启动后访问 `http://<主机>:8760`。

环境变量:

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RUNBOX_HOST` | `0.0.0.0` | 绑定地址(用 `0.0.0.0` 才能从别的机器访问) |
| `RUNBOX_PORT` | `8760` | 端口 |

> **在登录节点开发时**必须绑 `0.0.0.0`——`localhost` 用户从浏览器够不到。
>
> **从校外访问**建议走 SSH 端口转发或 Tailscale,直接暴露公网高位端口通常会被校园防火墙拦掉:
> ```bash
> ssh -L 8760:localhost:8760 <user>@<cluster>   # 然后浏览器开 http://localhost:8760
> ```

---

## 使用流程

1. **连接设置**(左侧导航):填一次集群信息(SSH 别名、用户名、Slurm account/partition/qos、默认 CPU/GPU/时长),测通后保存到 `~/.hpc-helper/config.toml`。本集群默认值已预填。
2. **① GPU 节点**:点「申请 GPU 节点」,分配过程实时显示(排队 → 启动 → 就绪)。
3. **② 我的项目**:填/浏览本地项目文件夹 → 扫描(列出 `.py` 与待同步文件)→ 同步到集群(增量 rsync)。
4. **③ 运行**:选脚本、填参数、点运行。输出在 ④ 实时流式显示。
5. **④ 输出**:看终端日志;结束后点「下载结果」把产物拉回本地。
6. 用完点「释放节点」归还 GPU。

---

## REST API

路由与引擎函数一一对应(全部定义在 `runbox/app.py`):

| 方法 & 路径 | 作用 |
|-------------|------|
| `GET  /api/session` | 顶部状态:是否已配置 + 当前持有的节点 |
| `GET  /api/config/defaults` | 集群默认值 + 当前配置(用于预填设置页) |
| `PUT  /api/config` | 保存设置到 `config.toml` |
| `POST /api/config/test` | 测试连接(不保存) |
| `GET  /api/node/up` | 申请 GPU 节点(**SSE**:status / done / error) |
| `POST /api/node/down` | 释放节点 |
| `GET  /api/project/browse` | 文件夹浏览器,列子目录 |
| `POST /api/project/scan` | 扫描本地项目(`.py` 列表 + 待同步文件) |
| `POST /api/project/push` | 增量同步项目到集群 |
| `POST /api/run` | 在节点上启动脚本 |
| `GET  /api/run/stream` | 运行输出(**SSE**:line / exit) |
| `POST /api/run/stop` | 停止当前运行 |
| `POST /api/pull` | 把结果下载到本地目录 |

引擎错误统一转成 `{"kind": ..., "message": ...}`(HTTP 400),前端按 `kind`(auth/config/alloc/sync)显示友好的中文提示。

---

## 当前状态

**已实现并验证可用:**
- 打开工作台、会话/配置读取、文件夹浏览、项目扫描
- 申请 GPU 节点 → 运行脚本(实时日志)→ 释放节点(已端到端验证:`local` 模式在登录节点跑通)
- 同步代码、下载结果、测试/保存连接

**仅入口、尚未实现**(导航中标注「即将上线」):
- 数据集 · 作业历史 · 协作空间 · 资源监控

---

## 已知限制

- **扫描包含 `.venv`**:`scan_project` 目前会把 `.venv/site-packages` 里的 `.py` 也列进脚本下拉框,造成噪音。需要在引擎层加隐藏目录/虚拟环境过滤。
- **单次运行**:MVP 同时只支持一个活跃运行。
- **参数解析简单**:运行参数按空格切分,不支持带引号的复杂参数。
- **登录节点长跑进程的 cwd 失效**:home 目录被 automount 在进程底下重挂载后,长期运行的服务进程 cwd 可能失效,导致 `sbatch: getcwd failed`。临时解法是从有效目录重启服务;根治方案是在引擎本地后端的 `subprocess` 调用里显式传 `cwd`。

---

## 项目结构

```
p107/
├── runbox/
│   ├── app.py            FastAPI 应用与所有路由
│   ├── engine.py         引擎的异步包装(worker 线程)
│   ├── __init__.py
│   └── static/
│       └── index.html    单页前端(内联 CSS/JS)
├── pyproject.toml
├── DESIGN.md / IDEA.md / PLAN.md   设计文档
└── README.md
```

---

## 开发笔记

- 前端是单个 `index.html`,由 FastAPI 的 `StaticFiles` 直接服务——**改完不用重启,刷新浏览器即可生效**。
- 改后端(`app.py` / `engine.py`)需要重启 uvicorn。
- 可用无头 Chrome 截图快速核对页面外观:
  ```bash
  google-chrome-stable --headless --disable-gpu --no-sandbox \
    --screenshot=/tmp/shot.png --window-size=1360,1500 http://127.0.0.1:8760/
  ```
