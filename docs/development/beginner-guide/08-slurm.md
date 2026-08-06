# 第八章：Slurm 开发必备知识

107 Workspace 把用户要求转换为作业并交给 Slurm，但不负责决定哪个作业先运行。开发者不必
掌握集群管理，只需理解作业、状态、资源和共享存储怎样影响应用。

## 8.1 最小术语表

| 概念 | 含义 |
| --- | --- |
| Job | 提交给集群的一次计算任务 |
| Partition | 一组用途或配置相近的计算节点 |
| Account | Slurm 中用于归属或计费的账号 |
| QoS | 优先级、时限等策略 |
| CPU、Memory、GPU | 作业申请的计算资源 |
| Time Limit | 作业允许的最长运行时间 |
| Exit Code | 程序退出码，通常 0 表示成功 |

典型状态如下：

```text
提交 → PENDING（排队）→ RUNNING（运行）→ 完成或失败
                                  \→ 取消
```

不同 Slurm 状态会映射为平台的 Run 状态。前端和业务代码使用平台枚举，不要到处复制 Slurm
字符串。

## 8.2 sbatch 脚本是什么

Slurm 作业脚本本质上是带资源声明的 Shell 脚本：

```bash
#!/bin/bash
#SBATCH --partition=gpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=8192M
#SBATCH --time=01:00:00
#SBATCH --gres=gpu:1

python train.py
```

项目由 `infrastructure/scheduler/script.py` 生成脚本，资源参数来自已经固定的 Run Snapshot。
环境变量不会直接写入可查看的脚本正文，以免 Secret 明文落盘。

真实平台的 Partition、GPU、Account 和 QoS 会变化，种子数据只是开发数据。代码和文档不能把
它们写成 107 集群的固定事实。

## 8.3 Scheduler Port

业务层只要求调度器提供三个操作：

```text
submit  提交任务并获得调度任务 ID
poll    查询调度任务状态
cancel  请求取消任务
```

取消通常是异步的：`cancel` 返回不等于任务已停止，最终状态仍由之后的 `poll` 决定。端口没有
“直接标记成功”的方法，平台必须相信实际调度结果。

当前提交链可以概括为：

```text
创建 Snapshot
→ 准备 work、inputs、logs
→ 在执行边界解析 Secret
→ submit 并保存 scheduler_job_id
→ 后台定期 poll
→ 映射 Run 状态
→ 终态后收集 Artifact
```

自动同步间隔由 `WORKSPACE107_RUN_SYNC_INTERVAL_SECONDS` 控制，设为 `0` 可关闭。单个 Run
同步失败时应记录日志并继续其他任务，不能因为查不到作业就猜测它成功。

## 8.4 Mock Scheduler

默认 Mock 并不“假装成功”，而是在 API 所在主机或容器启动真实子进程：

- POSIX 使用 Bash，Windows 使用系统命令解释器；
- stdout 和 stderr 写入 Run 日志；
- 状态与退出码来自真实进程；
- 没有 Slurm 排队、资源隔离、独立 Worker 或安全沙箱。

任何能提交 Run 的用户都能以 API 进程身份执行命令，因此 Mock 只能用于本地开发、自动化测试
和受信任演示，不能向不受信任用户开放。

Mock 会生成 `job.sh` 供检查，但当前子进程直接执行提交命令，不代表脚本中的所有环境准备步骤
或 Apptainer 环境都经过验证。API 重启还会丢失内存中的 Mock 作业登记。不要用 Mock 结果证明
真实 Slurm 路径可用。

## 8.5 Slurm REST Adapter

把 `WORKSPACE107_SCHEDULER` 设为 `slurm` 后，Adapter 会调用 slurmrestd 提交、查询和取消作业。
还需配置 API 地址、用户和 JWT。JWT 等价于密码，只能在运行时注入。

当前代码包含状态映射与错误处理，但尚未在真实 107 集群完成 API 版本、认证、网络、Partition、
Account、QoS 和资源限制验收。因此“代码存在”“配置能切换”和“生产接入完成”是三个不同结论。

## 8.6 运行目录和 Artifact

本地存储可简化为：

```text
storage_root/
├── blobs/
├── runs/<run_id>/
│   ├── work/
│   ├── inputs/
│   ├── logs/stdout.log
│   ├── logs/stderr.log
│   └── job.sh
└── artifacts/<artifact_id>/
```

API 准备 `work` 和只读输入，计算任务写日志和结果。结束后，平台按 Snapshot 的规则从工作目录
收集 Artifact。必需 Artifact 缺失时，即使程序退出码为 0，Run 仍可能判定失败。

## 8.7 为什么必须使用共享存储

真实 Slurm 场景中，API 和计算节点是不同机器：

```text
API 写入运行目录
       |
       v
共享文件系统
       ^
       |
计算节点读取输入并写回结果
```

两侧必须用同一绝对路径看到同一内容。当前容器内应用路径固定为
`/var/lib/workspace107/storage`。单机 Docker 命名卷通常对计算节点不可见，不能直接作为集群
共享存储。

真实接入至少要验证路径一致、UID/GID 权限、Input Binding 只读以及日志和 Artifact 的并发
读写。应用代码通过不代表这些外部条件成立。

## 8.8 调度问题的排查顺序

| 现象 | 优先检查 |
| --- | --- |
| Run 一直不变化 | 同步间隔、后台同步日志和 `scheduler_job_id` |
| Mock Run 变成未知 | API 是否重启，子进程登记是否丢失 |
| Slurm 提交失败 | REST 地址、版本、用户、JWT、Account、Partition、QoS |
| 程序退出 0 但 Run 失败 | 必需 Artifact 是否存在于指定路径 |
| API 能看到文件，计算节点看不到 | 两侧挂载是否为同一文件系统和同一绝对路径 |

排查真实 Slurm 问题时记录 Adapter 请求结果、调度任务 ID 和应用 `request_id`，但不要把 JWT、
完整环境变量或 Secret 写进日志和 Issue。

