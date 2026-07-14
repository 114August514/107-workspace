# 参考项目吸收与独立性

本轮重初始化的原则不是复制旧项目结构，而是提取可验证的行为，再通过本项目的
领域端口和基础设施 adapter 重新实现。活动后端因此可以独立安装、测试和演进。

## 1. 吸收总表

| 来源 | 吸收的行为 | 本地落点 | 明确排除 |
| --- | --- | --- | --- |
| RunBox | SSE 日志、非阻塞外部调用、稳定错误类别、显式停止和结构化完成信息 | Run API、领域错误、ClusterPort、reconciler | 单体大路由、全局 active run、字典 payload、捆绑 SPA、隐式 `hpc_helper.api` |
| `submit107` | 入口与依赖推断、preflight、严格 sbatch、Slurm 解析、传输与调度分离 | `application/inference.py`、`preflight.py`、Slurm renderer/parser/adapter | CLI prompt、Rich UI、Markdown run record、notebook 重写、Git/Pan 编排、CLI 配置 |
| `hpc-helper` | SSH 连接选项、PAX tar、双进程清理、`.hpcignore`、manifest、增量扫描、local/SSH 模式、队列对账 | SSH transport、tar stream、scanner、transfer、Slurm adapter | 单用户 session、`sys.exit`、终端 UI、不安全路径与 shell 插值、自动远程删除 |

## 2. RunBox

原 RunBox 证明了几个交互模式：FastAPI 可以承载集群操作和 SSE 输出；阻塞集群
调用不能阻塞事件循环；运行需要显式取消和稳定错误类别。

这些行为在新后端中被扩展：

- 单向 SSE 改为带 offset 的可重连日志流；
- 进程级 active run 改为数据库持久状态和 RunEvent 历史；
- 直接集群调用改为 ClusterPort；
- 取消改为应用用例、adapter 合同和 reconciler 共同处理；
- 字典请求体改为 Pydantic schema；
- 外部错误改为稳定领域错误和 Problem Details。

旧源码完整移动到
[../../../archive/runbox-v0/](../../../archive/runbox-v0/)，只用于追溯。归档中的代码仍引用
本地不存在的 `hpc_helper.api`，因此不承诺它可以从归档目录独立运行。

## 3. submit107

`submit107` 提供了较成熟的单用户提交行为。本项目吸收了适合服务端的部分：

- 项目入口检测；
- 基于 `pyproject.toml` 等文件的环境和资源推断；
- 可解释的 preflight 检查；
- 严格 sbatch 模板与资源 directive；
- `sinfo`、`sbatch`、`squeue`、`sacct`、`scancel` 调用和输出解析；
- 本地项目传输与集群调度之间的职责分离。

没有吸收 CLI 交互、终端展示、notebook 改写、Markdown 运行记录、Git/Pan 自动化和
CLI 配置层。这些能力要么不适合多用户 HTTP 服务，要么属于后续产品层。

## 4. hpc-helper

设计时参考的本地版本是 `dedae742e7fa8f8ebb103b9eb62e8cbe8d28dbf3`。
吸收重点集中在远程执行和项目传输：

- SSH 禁用 ControlMaster，并配置连接超时和 keepalive；
- PAX tar 流支持 Unicode 路径；
- writer 或 reader 失败、取消、启动失败时清理两个进程；
- `.hpcignore` 和目录剪枝；
- manifest 增量扫描；
- local 登录节点和 SSH 驱动两种显式模式；
- `squeue` 到 `sacct` 的状态恢复与对账思想；
- account、partition、qos 和资源字段。

没有继承全局单用户 session、`sys.exit`、终端输出、未经校验的路径组合、shell
字符串插值、静默忽略损坏状态或自动删除远程旧文件。

### Batch grouping 偏差

设计证据提到了 `hpc-helper` 的 batch groups，但当前活动代码没有 batch/group
领域模型、应用用例或 HTTP API。Slurm parser 对 `.batch` step 的识别只是作业记账
解析，不等于实现 batch grouping。审阅和后续文档都不应把该能力标记为已完成。

## 5. 独立性证据

以下扫描在后端验收时无匹配：

```bash
rg -ni 'runbox|submit107|hpc[-_]helper' \
  backend/src backend/pyproject.toml backend/uv.lock

rg -n 'workspace107\.(api|application|infrastructure)' \
  backend/src/workspace107/domain

rg -n 'workspace107\.(api|infrastructure)' \
  backend/src/workspace107/application

rg -n 'shell\s*=\s*True|create_subprocess_shell|os\.system' backend/src
```

其他证据：

- `backend/pyproject.toml` 和 `backend/uv.lock` 不声明三个参考项目为依赖；
- 本地 `hpc-helper/` checkout 被根 `.gitignore` 忽略，`git ls-files hpc-helper` 为空；
- `submit107` 是同级参考仓库，不在 `107-workspace` 版本树内；
- 旧 RunBox 只存在于 `archive/runbox-v0/`；
- 仅 SSH transport 使用 `shlex.join` 构造一个被引用的远程命令；
- 活动源码没有 `shell=True`、`create_subprocess_shell` 或 `os.system`。

## 6. 审阅判断标准

吸收是否成功，不应以“代码看起来相似”为标准，而应检查：

1. 行为是否通过本项目自己的端口表达；
2. 应用层是否不知道具体参考项目和 transport；
3. 路径、命令、状态和错误是否经过本项目的验证与归一化；
4. 行为是否有独立测试，不需要参考仓库或真实凭据即可运行；
5. 未吸收范围是否被明确记录，而不是悄悄保留隐式依赖。
