# ADR-0004 RuntimeBackend：Native / Conda / Apptainer

状态：已接受 · 阶段：M2 · 相关：GR-011、GR-015

## 背景

M1 的 `EnvironmentVersion` 有一个 `image` 字段，值形如 `python:3.12-slim`。
但实际上：

- mock 适配器**完全忽略**它，直接在宿主机上跑 `submission.command`
- Slurm 适配器渲染的 sbatch 脚本里也没有它，只有一行裸命令

也就是说「运行环境」这个概念目前只到了展示层，没有真正生效。

参考材料
[workspace-slurm-apptainer-context.md](../references/platform/workspace-slurm-apptainer-context.md)
说明了 107 集群的真实情况：

- 集群预装 Apptainer 1.4.5，和 Python、CUDA、Conda 一样属于软件运行环境
- 真实作业脚本长这样：

  ```bash
  module load apptainer/1.4.5
  apptainer exec --nv /public/images/pytorch.sif python train.py
  ```

- 而且明确要求把系统设计成 `RuntimeBackend` 下分 Native / Conda / Apptainer，
  **Apptainer 是可调用的一种能力，不是必须**

同时它还提了一条底线：核心链路要能真实对接 107 环境，而不是做一个模拟界面。

## 决策

### 1. EnvironmentVersion 增加 runtime_backend 与对应参数

```text
EnvironmentVersion
├── runtime_backend    native | conda | apptainer
├── image              仅 apptainer：.sif 路径或镜像引用
├── conda_env          仅 conda：环境名
├── modules            需要 module load 的模块列表（可为空）
└── setup_command      三种方式都可以有的额外准备命令
```

字段按 backend 取用，不合法的组合在发布环境版本时就拒绝——
不要等到提交作业才发现 apptainer 环境没填 `.sif` 路径。

### 2. 作业脚本渲染按 backend 分派

现在 `infrastructure/scheduler/script.py` 只有一种渲染方式。改成分派：

```text
native      [module load ...] → [setup_command] → <command>

conda       [module load ...] → conda activate <env> → [setup_command] → <command>

apptainer   module load apptainer/<版本>
            apptainer exec [--nv] [--bind ...] <image> bash -lc "<setup> && <command>"
```

`--nv` 只在算力请求含 GPU 时加。这一点很重要：CPU 分区上加 `--nv` 会直接报错。

### 3. Input Binding 的挂载方式由 backend 决定

这是 RuntimeBackend 和 [ADR-0002](0002-shared-resource-grants.md) 的接缝，
也是把它放进 M2 的主要理由：

```text
native / conda
└── 平台把内容准备到 Run 目录下，通过 $WORKSPACE107_INPUTS_DIR 暴露

apptainer
└── apptainer exec --bind <宿主路径>:<access_path>:ro
    access_path 在容器里就是真正的绝对路径
```

Apptainer 这条更贴近设计稿 §3.1.3 的原意——`/inputs/train` 就是 `/inputs/train`，
而不是「相对于某个环境变量的路径」。M1 用环境变量是本机执行下的权宜之计，
不是目标形态。

只读用 `:ro` 挂载，天然满足 GR-011。

### 4. mock 适配器如实渲染，但仍然本机执行

mock 的价值在于**不连集群也能跑通完整闭环**。它继续在宿主机上直接执行命令，
但要把按 backend 渲染出的完整作业脚本写进 `runs/<run_id>/job.sh`，
让用户看到「如果提交到集群，平台会生成什么」。

这样做的好处是：脚本渲染逻辑在 mock 模式下也被真实执行的测试覆盖到，
不会出现「本地一切正常，一上集群脚本就错」。

**不做的事**：让 mock 真的去调用本机的 apptainer。开发机上通常没有，
装了也和集群的版本、镜像路径对不上，徒增一层假象。

### 5. 版本号、镜像路径、分区名一律不写死

Apptainer 版本、`.sif` 存放路径、可用分区、GPU 型号都是会变的平台事实。

```text
代码里    从 EnvironmentVersion 和 ComputePlan 读，不出现常量
文档里    写「以平台页面为准」，并给出确认方式
种子数据  标注为演示值
```

M1 的 seed 脚本已经这么做了，M2 继续保持。

## 放弃的方案

**只支持 Apptainer。** 参考材料明确说了 Apptainer 不是必须。而且用户如果只想跑
一个纯 Python 脚本，强制套一层容器是没必要的负担。

**把作业脚本模板做成可配置文件让用户自己写。** 那等于把 Slurm 的复杂度又还给了用户，
和产品价值（「他只知道：选择项目、选择环境、选择资源、点击运行」）背道而驰。
平台管理员可以管理环境定义，普通用户不碰脚本。

**让 mock 适配器也走 apptainer。** 见第 4 条。

**用 Docker 而不是 Apptainer 跑用户作业。** HPC 集群通常不给普通用户 Docker 守护进程
的访问权（那等于给 root）。Apptainer 正是为这个场景设计的。
本仓库的 Docker 只用于部署 107 Workspace 应用自身，
见 [ADR-0005](0005-deployment-topology.md)。

## 影响

- `EnvironmentVersion` 加字段 → 需要一次 Alembic 迁移
- `script.py` 从单一函数拆成按 backend 分派，每种 backend 的脚本内容都要有测试
  （字符串断言，不需要真集群）
- `SchedulerSubmission` 需要携带输入挂载信息，现在只有 `work_dir`
- `LocalStorage.prepare_run_directory` 的 `copytree` 要换成只读挂载或链接，
  否则大数据集不可用（与 [ADR-0002](0002-shared-resource-grants.md) 第 7 条同一件事）
- 种子数据要给三种 backend 各准备一个示例环境，方便演示和测试
