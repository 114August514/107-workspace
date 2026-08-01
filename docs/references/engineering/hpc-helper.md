# hpc-helper 来源记录

`hpc-helper` 是迁移前用于理解 SSH、Slurm 和文件传输行为的外部参考项目，不是
107 Workspace 的依赖，也不在本仓库中 vendoring 源码。

| 项目 | 值 |
| :--- | :--- |
| 上游 | <https://github.com/Ressula/hpc-helper> |
| 固定提交 | [`dedae742e7fa8f8ebb103b9eb62e8cbe8d28dbf3`](https://github.com/Ressula/hpc-helper/tree/dedae742e7fa8f8ebb103b9eb62e8cbe8d28dbf3) |
| 核验日期 | 2026-08-01 |
| 本地核验状态 | `main` 与 `origin/main` 一致，工作区干净 |

迁移前实现从中参考过 SSH 连接选项、PAX tar 流、双进程清理、忽略文件扫描、manifest
和调度队列恢复等思路。活动实现已经把需要的行为重新建模到自己的端口和基础设施中，
`backend/`、`frontend/`、`scripts/` 与 CI 均不导入或调用 `hpc_helper`。

固定提交没有许可证、测试或锁文件，也没有旧 RunBox 所描述的 `hpc_helper.api` 模块。
因此把源码复制到本仓库既不能恢复 RunBox 的可运行性，也会引入不必要的授权边界。
需要审查原实现时直接查看固定上游提交；需要本地 checkout 时使用：

```bash
git clone https://github.com/Ressula/hpc-helper.git
git -C hpc-helper checkout dedae742e7fa8f8ebb103b9eb62e8cbe8d28dbf3
```
