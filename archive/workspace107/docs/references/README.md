# 参考材料

这里放**塑造了产品设计的原始材料**：平台事实、培训内容、外部约束。

它们是设计依据，不是需求文档，也不会自动更新。读的时候注意两点：

- 里面提到的软件版本、分区名、路径、配额都是**记录当时的情况**，
  实际取值以平台页面和集群配置为准
- 和 [产品设计最终稿](../product/design-final.md) 冲突时，以设计稿为准；
  如果冲突说明设计需要重新评审，应该开 Issue 讨论，而不是私下按某一份改

## 目录

| 文件 | 内容 |
| :--- | :--- |
| [platform/workspace-slurm-apptainer-context.md](platform/workspace-slurm-apptainer-context.md) | 107 Workspace 与 Slurm、SCOW、Apptainer 的层级关系，以及产品边界 |

## 这份材料为什么重要

`workspace-slurm-apptainer-context.md` 定下了两条底线，直接影响了架构：

```text
1. 107 Workspace 不替换 Slurm、SCOW、Apptainer 和共享存储，
   而是建立在它们之上，把空间、项目、数据、环境、算力、作业、
   日志和结果组织成完整工作流。

2. 核心链路「创建 Run → 生成作业 → 提交 Slurm → 查询状态 → 获取日志与结果」
   必须能真实对接 107 环境，而不是做一个模拟界面。
```

第一条对应 [GR-015](../domain/invariants.md)（Slurm 是实际调度状态的事实来源）
和 [ADR-0004](../decisions/0004-runtime-backend.md)（RuntimeBackend 抽象）。

第二条是 M2 把 RuntimeBackend 补齐的直接理由——现在的
`EnvironmentVersion.image` 还没有真正生效，见
[M2 Milestone](../milestones/M2-collaborative-workspace.md)。

## 还有哪些材料没放进来

原始培训材料里还有两份 PDF（107 集群竞赛培训、算力平台赛道介绍）。
它们体积较大且不适合放进普通 Git，需要时按 [Git 使用指南](../development/git-guideline.md)
第五节的规则评估是否用 Git LFS，或者直接从原始渠道获取。
