不是替换 Apptainer。**107 Workspace 和 Apptainer 根本不在同一个层级。**

你可以先记住：

> **107 Workspace 是用户真正使用的算力平台应用；Apptainer 是底层用于运行计算任务的一种容器技术。**

培训材料里，107 集群已经预装了 Apptainer 1.4.5，和 Python、CUDA、Conda 一样属于软件运行环境；用户通过 Slurm 提交作业，计算节点执行任务。

## 用你的系统画出来

```text
                    用户

                     │
                     ▼

              107 Workspace
        用户真正直接使用的产品

                     │
       ┌─────────────┼─────────────┐
       │             │             │

       ▼             ▼             ▼

   Workspace       Project        Run
   协作空间        项目管理       一键运行

                     │

                     ▼

                RunService
               组织运行流程

                     │

       ┌─────────────┼─────────────┐
       │             │             │

       ▼             ▼             ▼

   Scheduler       Storage       Runtime
    调度能力        存储能力      运行环境能力

       │             │             │

       ▼             ▼             ▼

     Slurm         /public      Apptainer
                                Conda
                                Native
```

所以层级关系是：

```text
107 Workspace
      ↓
使用 Slurm 调度计算资源
      ↓
Slurm 启动作业
      ↓
作业可以使用 Apptainer 运行
      ↓
Python / PyTorch / 用户程序
```

举一个具体例子。

用户进入 107 Workspace：

```text
项目：图像分类实验

数据集：CIFAR-10

运行环境：
PyTorch 2.x + CUDA 13

资源：
1 GPU
8 CPU
32 GB RAM

入口：
python train.py
```

点击：

```text
[开始运行]
```

107 Workspace 内部：

```text
1. 检查用户权限

2. 检查 Project 和 Dataset

3. 创建 Run

4. 准备运行目录

5. 生成 Slurm Job Script

6. 根据运行环境生成 Apptainer 命令

7. 提交给 Slurm

8. Slurm 分配计算节点

9. Apptainer 启动容器

10. train.py 开始执行

11. Workspace 查询作业状态

12. 收集日志和结果
```

最终实际可能生成：

```bash
#!/bin/bash

#SBATCH -p P107-RTX5090
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8

module load apptainer/1.4.5

apptainer exec \
    --nv \
    /public/images/pytorch.sif \
    python train.py
```

用户完全可以不知道：

```text
Slurm

sbatch

module

Apptainer

/public/xxx

.sif
```

他只知道：

```text
选择项目

选择环境

选择资源

点击运行
```

这才是 107 Workspace 的产品价值。

---

还有一个容易混淆的问题：**107 Workspace 是否必须使用 Apptainer？**

也不是。

你应该把系统设计成：

```text
                  RuntimeBackend

                        │

          ┌─────────────┼─────────────┐
          │             │             │

          ▼             ▼             ▼

    NativeRuntime   CondaRuntime   ApptainerRuntime
```

例如用户选择：

```text
运行环境：

○ 平台 Python 环境

○ Conda 环境

● Apptainer 容器环境
```

Workspace 根据选择生成不同的 Job Script。

所以：

> **Apptainer 是 107 Workspace 可以调用的一种运行环境能力，而不是 107 Workspace 要替换的系统。**

再往大一点看，你们真正想做的是：

```text
                   用户

                    │
                    ▼

             107 Workspace
           算力使用工作流平台

                    │

       ┌────────────┼────────────┐
       │            │            │

       ▼            ▼            ▼

    Slurm        Storage      Runtime System

                                  │

                       ┌──────────┼──────────┐

                       ▼          ▼          ▼

                    Native      Conda    Apptainer
```

因此，我建议你从项目第一版就明确产品边界：

> **107 Workspace 不替换 Slurm，不替换 SCOW，不替换 Apptainer，也不替换共享存储。它建立在这些现有基础设施之上，把空间、项目、数据、运行环境、算力资源、作业、日志和结果组织成一个面向本科生真实使用的完整工作流。**

其中有一点尤其重要：**107 Workspace 应该是能真实部署、真实连接 107 集群、真实提交 Slurm 作业的产品，而不是为了比赛做一个模拟界面。**

MVP 可以暂时用 SQLite、本地身份认证、假数据演示部分功能；但最核心的 `创建 Run → 生成作业 → 提交 Slurm → 查询状态 → 获取日志与结果` 这条链路，建议一定对接真实 107 环境。这样你们的作品才真正属于“算力平台功能开发”。
