# 0005. 完整开发与运行只支持 Linux / WSL2

- 状态：已接受
- 日期：2026-08-26

## 背景

统一 Python task CLI 只决定怎样调用工程任务，不承诺跨平台运行。M1 Run workspace 依赖 POSIX
UID/GID、shared GID、setgid、descriptor-relative file operations、signal、同文件系统 atomic rename
和 PostgreSQL advisory lock。原生 Windows 不提供同一组语义；用 shim 模拟会削弱权限与恢复保证。

## 决定

| 平台 | 开发与工程检查 | M1 Worker / Shared FS / smoke / deploy |
| :--- | :--- | :--- |
| Linux | 支持 | 完整本地运行目标；真实 107 仍受 human gate 约束 |
| WSL2 | 按 Linux 语义支持；仓库、storage、PostgreSQL 数据必须位于 Linux filesystem | 与 Linux 相同；Ubuntu 结果不能冒充 WSL2 实机证据 |
| 原生 Windows / PowerShell | 不支持 | 不支持；Worker 配置阶段 fail-fast |

`scripts/workspace.py` 仍是唯一 task 实现，Makefile 是薄转发；这不构成原生 Windows support。
CI 与文档不得把跨平台 Python 语法或 MockScheduler 的 adapter 分支表述成完整平台证据。

## 后果

- 不新增 Windows RunWorkspace、ACL 模拟层或降级权限 fallback。
- Linux 负责 Compose + PostgreSQL + API + external Worker + Mock Scheduler smoke。
- WSL2 持久数据不得放在 `/mnt/c` 等 Windows filesystem mount。
- 只有出现明确的原生 Windows 产品义务，并给出独立 Shared-FS/ACL、路径安全、恢复、PostgreSQL
  和部署验收标准时，才重新评估。

---
> 决策变更时新增 ADR，并将本记录标为被取代，不重写历史。
