# 0004. 区分完整 Linux 运行目标与原生 Windows contributor 基线

- 状态：已接受
- 日期：2026-08-11

## 背景

ADR-0001 决定用跨平台 Python 任务入口统一开发命令，Makefile 只做薄转发，平台脚本只
留在边缘。该决定统一了“怎样调用任务”，但没有承诺每个运行时能力都能在所有宿主平台
实现。

ADR-0003 随后把 M1 Run workspace 建立在 POSIX Shared FS、service/compute UID、共享 GID、
setgid mode、descriptor-relative `openat`/`O_NOFOLLOW` 和同文件系统 atomic rename 上；独立
Worker 还要求 PostgreSQL。原生 Windows 不提供这组语义。继续把 Windows contributor CI
称为完整 Worker smoke，会把任务入口可移植性误写成运行拓扑可移植性。

## 决定

平台支持以本 ADR 为唯一长期决策来源；其他入口只保留简短说明和链接。

| 平台 | Contributor setup/check | 本地开发面 | M1 Worker / Shared FS / smoke / deploy |
| :--- | :--- | :--- | :--- |
| Linux | 支持 | 完整 API、前端、Git、PostgreSQL、Worker 与 Mock | 完整开发运行目标；真实 107 仍受独立 human gate 约束 |
| WSL2 | 按 Linux 语义支持 | 与 Linux 相同，但仓库、storage 和 PostgreSQL 数据必须位于 Linux filesystem | 与 Linux 相同；Ubuntu CI 不能冒充 WSL2 实机证据 |
| 原生 Windows | 保留无 Make 的 `setup` / `check`、前端、API、Git 和 MockScheduler NT 分支 | 可开发和检查这些 contributor surface | 不支持；Worker 必须在启动配置阶段清晰 fail-fast |

`workspace.py` 仍是唯一任务实现。原生 Windows 运行同一个 `check` 任务图，但明确依赖
POSIX UID/GID、signal 与文件系统语义的 adapter tests 在 non-POSIX 平台按模块跳过；这不是
Windows shim，也不把 Ubuntu 结果表述成 Windows 运行证据。

CI 对应关系：

- Ubuntu canonical check 验证完整仓库检查；Linux Compose + PostgreSQL + Worker smoke
  验证本地完整运行切片。
- Windows runner 只验证 contributor setup 与 canonical check，不运行 M1 HTTP Worker smoke。
- 原生 Windows 的最终兼容性仍以 Windows runner 为准，不能由 Linux monkeypatch 代替。

## 后果

- 保留 Windows 协作者有价值的统一入口、PowerShell bootstrap、CRLF/LF 约束和平台调度分支。
- 不新增 `WindowsRunWorkspace`、ACL 模拟层或对 POSIX 权限的不真实兼容实现。
- `make smoke` / `workspace.py smoke`、独立 Worker 和部署文档默认指向 Linux/WSL2；原生
  Windows 用户应使用 WSL2，并把持久数据放在 Linux filesystem，而不是 `/mnt/c` 等
  Windows 挂载目录。
- 平台特定测试 skip 必须对应真实运行依赖，不能用于掩盖本应跨平台的 API、Git、前端或
  公共任务入口回归。

## 与既有 ADR 的关系

本 ADR **细化但不取代 ADR-0001**：跨平台 Python 任务入口继续有效，变化只是明确其能力
边界。本 ADR与 ADR-0003 一致：M1 B/C 接缝继续使用 POSIX Shared FS 与独立 Worker，不因
Windows contributor CI 引入第二套运行平台。

## 重新评估条件

只有出现明确的原生 Windows 完整运行需求，并能给出 Windows Shared-FS/ACL、路径安全、
进程恢复、PostgreSQL 与目标部署的独立验收标准时，才评估新的运行 adapter。CI 变红或
已有 Windows contributor 入口本身不构成该需求。
