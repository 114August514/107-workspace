# Platform Reference Materials

These materials document the environment in which 107 Workspace is intended
to operate. They were collected on 2026-07-14 and are informative rather than
normative product specifications. Operational details such as versions,
partitions, endpoints, and examples may change over time and should be checked
against the live platform before use.

## Sources

### 中国科大“一〇七杯”算力与智能体开发大赛算力平台赛道培训

[107-cluster-competition-training.pdf](107-cluster-competition-training.pdf) is
the original 59-page training deck. It covers platform architecture, Slurm
concepts and commands, SCOW operation, REST APIs, monitoring, examples, and
troubleshooting. The PDF content is preserved unchanged.

### 算力平台及算力平台赛道介绍

[computing-platform-track-introduction.pdf](computing-platform-track-introduction.pdf)
is the original 8-page overview. It provides a concise introduction to compute
clusters, getting started, and selecting a competition topic. The PDF content
is preserved unchanged.

### 107 Workspace、Slurm 与 Apptainer 职责说明

[workspace-slurm-apptainer-context.md](workspace-slurm-apptainer-context.md)
explains how the product layer, scheduler, storage, and runtime environment
relate. It helps distinguish what 107 Workspace owns from capabilities it uses
below the application layer.

For current backend boundaries and accepted scope, use the
[backend specification](../../superpowers/specs/2026-07-13-workspace107-backend-design.md).
