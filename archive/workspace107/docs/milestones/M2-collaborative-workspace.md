# M2 - Collaborative Workspace

## 目标

让一个协作空间里的多名成员**共享数据、复用彼此的成果、看见彼此的动作**，
并且清楚这个空间的资源用到了什么程度。

M1 证明了「一个人能把作业跑完」。M2 要证明「一群人能在同一个空间里一起干活，
而且不会互相踩到」。

## 用户结果

```text
教师 / 队长
├── 按角色分配权限，而不是所有人都能改一切
├── 维护一份共享数据集，成员的 Project 引用它，不用每人复制一份
└── 看到空间用了多少存储、还剩多少，并清理不再需要的日志和产物

成员
├── 从别人的确定版本 Fork 出自己的 Project，起点一致但互不影响
├── 引用 Workspace 提供的共享资源作为 Run 输入
└── 作业结束、被邀请、权限变化时收到通知，不用一直盯着页面刷
```

## 范围

对应 [产品设计最终稿](../product/design-final.md) 中的这些章节：

| 设计稿章节 | M2 覆盖内容 | 阶段标记 |
| :--- | :--- | :--- |
| 2.2 A | Workspace 归档与恢复 | V1 |
| 2.2 C | Admin / Viewer 扩展角色、修改成员角色 | V1 |
| 2.4 A | 从确定 Project Version 派生新 Project（含跨 Workspace） | Core |
| 2.4 B | Fork Relation 来源追踪，从来源信息进入原 Project | Core |
| 2.6 A | 浏览与查看当前 Workspace 可发现的共享资源 | Core |
| 2.6 B | Project 关联资源版本、配置访问位置、更换与解除关联 | Core |
| 2.6 C | 创建共享资源、上传形成版本、发布新版本 | Core |
| 2.6 D | 查看资源所有者与共享范围、授权给指定 Workspace、撤销授权 | Core / V1 |
| 2.6 E | 查看引用共享资源的 Project 与近期 Run | V1 |
| 2.10 A | 通知中心：查看、未读数、标记已读、从通知进入对象 | Core |
| 2.10 B | Run 结束或异常、成员与权限变更、资源不可用通知 | Core |
| 2.10 D | Workspace 与 Project 的近期活动 | Core |
| 2.12 A | 使用概览：主要数据和资源占用、额度上限与剩余 | Core |
| 2.12 B | 数据保留与清理：清理日志和 Artifact、保留标记、影响检查 | Core |
| 2.5 D | RuntimeBackend：Native / Conda / Apptainer | — |

### 为什么把 RuntimeBackend 放进 M2

它不是协作能力，但有两个理由必须在这一阶段解决：

1. **M1 留下的真实缺口。** `EnvironmentVersion.image` 目前被 mock 适配器完全忽略，
   Slurm 适配器生成的 sbatch 脚本里也没有 `module load apptainer` 和
   `apptainer exec --nv`。参考材料
   [workspace-slurm-apptainer-context.md](../references/platform/workspace-slurm-apptainer-context.md)
   明确要求核心链路能真实对接 107 集群，这个缺口不补，那条底线就立不住。
2. **它和 Shared Resource 的设计耦合。** Input Binding 的 access_path 在 Apptainer
   下就是 `--bind` 的目标路径，在 Native / Conda 下则要靠环境变量暴露。
   不先定下 RuntimeBackend，共享资源的挂载方式就是悬空的。

详见 [ADR-0004 RuntimeBackend](../decisions/0004-runtime-backend.md)。

## 非目标

写清楚不做什么，比写做什么更重要。以下能力**不在 M2**：

| 不做 | 归属 |
| :--- | :--- |
| 模板发布、发现与模板库治理 | §2.4 C/D/E，V1 |
| Course Profile、Assignment、Submission | §2.11，M3 |
| 权益申请与审批流程 | §2.2 D，V1 |
| 外部 Git 仓库导入、连接与同步 | §2.3 D，V1 |
| 分支、Merge Request、代码评审 | §2.3 C，V1/V2 |
| 邮件通知、免打扰时段、通知摘要、订阅 | §2.10 C，V1/V2 |
| 指标上报与多 Run 结果比较 | §2.9 D，V1/V2 |
| 平台管理与运维后台 | §2.13，独立阶段 |
| 自定义角色、成员组、Project 级细粒度权限 | §2.2 C，V2 |
| 资源使用统计、来源与派生关系图 | §2.6 E，V2 |

M2 的通知**只做站内**。邮件通道在 V1 加，但出口接口在 M2 就要留好
（见 [ADR-0003](../decisions/0003-activity-and-notification.md)）。

## 关键设计决策

开工前先定下来，避免边写边改：

| 决策 | 记录 |
| :--- | :--- |
| Fork 复制什么、不复制什么，如何追踪来源 | [ADR-0001](../decisions/0001-fork-semantics.md) |
| Shared Resource 的归属、版本与跨 Workspace 授权 | [ADR-0002](../decisions/0002-shared-resource-grants.md) |
| 活动与通知为什么是两条独立的数据流 | [ADR-0003](../decisions/0003-activity-and-notification.md) |
| Native / Conda / Apptainer 三种运行方式如何统一 | [ADR-0004](../decisions/0004-runtime-backend.md) |

## 开工前的加固（已完成）

M2 动手之前先补掉了 M1 留下的几个「只在单用户、小数据量下成立」的问题。
它们不属于协作主题，但会被 M2 直接放大，所以先做：

| 加固 | 对 M2 的意义 |
| :--- | :--- |
| 提交路径的并发串行化 | Fork 和资源发布同样是「先查后写」，直接复用这套模式 |
| 幂等键机制 | Fork、发布资源版本、批量邀请都需要，接口和表已经在了 |
| 分页信封 | 活动流和通知中心是天然无界的列表，契约形状先定好，不用回头改 |
| request_id 与结构化日志 | 协作场景排查「谁在什么时候做了什么」要靠它 |
| 就绪探针 | 与 M2 无关，但部署要用 |

详见 [ADR-0007](../decisions/0007-submission-correctness-and-observability.md)。

**M2 需要注意的两处衔接**：

- 幂等登记目前只增不删。M2 做数据保留与清理（§2.12 B）时一并给它加清理策略。
- 活动流如果要稳定的无限滚动，应当新增游标分页模型，**不要改现有的 offset 模型**。

## 完成标准

- [x] Owner 可以把成员设为 Admin / Viewer；Viewer 能看不能改，不能创建 Run
- [x] 成员 A 的 Project Version 可以被成员 B Fork 到自己的 Personal Workspace，
      两边后续修改互不影响
- [x] Fork 不带走源空间的成员权限、资源权益、凭据、Run 历史、日志和 Artifact（GR-006）
- [x] Fork 复制的 Secret 引用表达式在目标空间缺少同名 Secret 时显示为未解析状态，
      提交前检查拦下（GR-012 规则 4）
- [ ] Workspace 可以创建 Shared Resource 并发布版本；多个 Project 引用同一份内容
      只占一份存储
- [ ] Shared Resource 可以授权给另一个 Workspace；撤销授权后新 Run 被提交前检查拦下，
      已有 Run 的快照和历史记录不变（GR-007 / GR-008）
- [ ] 未被授权的 Shared Resource 不出现在列表和搜索里，直接访问返回 404（GR-013）
- [ ] Run 结束、失败、成员变更会产生站内通知，未读数正确，点击能进入对应对象
- [ ] Workspace 与 Project 活动流记录操作者、时间、对象、动作，可以从活动进入对象
- [ ] 使用概览显示 Project 文件、Run 日志、Artifact 和共享资源的占用量
- [ ] 清理 Artifact 后内容消失，但标识、名称、摘要、大小、产生时间和清理状态
      仍保留在历史 Run 中（GR-016）
- [ ] 清理前会列出受影响的运行方案和 Run
- [ ] Slurm 适配器能按 RuntimeBackend 生成 native / conda / apptainer 三种作业脚本，
      脚本内容有测试覆盖
- [ ] 前端控制台可以完成上述全部操作
- [ ] `scripts/check.sh` 全绿

验收方式：

```bash
./scripts/demo-collab.sh   # M2 新增：两个用户在一个协作空间里的完整流程
./scripts/check.sh
```

## 拆分建议

一个 Issue 控制在半天到三天。建议按下面的顺序推进——前两项是后面所有工作的地基：

| # | Issue | 类型 | 依赖 | 说明 |
| :-- | :--- | :--- | :--- | :--- |
| 1 | ~~AccessGuard 从「角色比较」重构为「能力判断」~~ | `refactor` | — | **已完成**，见 [ADR-0008](../decisions/0008-capability-based-authorization.md) |
| 2 | ~~Admin / Viewer 角色与角色修改~~ | `feat` | 1 | **已完成**，含 11 条越权拦截测试 |
| 3 | 活动记录：ActivityRecorder 与 Workspace / Project 活动流 | `feat` | 1 | **已完成** |
| 4 | 通知中心：NotificationPublisher 端口与站内通知 | `feat` | 3 | **已完成** |
| 5 | Fork：从确定版本派生 Project 与来源追踪 | `feat` | 1 | **已完成** |
| 6 | Shared Resource：对象、版本与内容上传 | `feat` | — | 对应 ADR-0002 |
| 7 | Shared Resource：Project 关联与 Run 输入 | `feat` | 6 | 复用已有 Input Binding |
| 8 | Shared Resource：跨 Workspace 授权与撤销 | `feat` | 6 | 重点测 GR-007 / GR-008 / GR-013 |
| 9 | RuntimeBackend：Native / Conda / Apptainer 脚本渲染 | `feat` | — | 对应 ADR-0004，可与 5~8 并行 |
| 10 | 使用概览与数据清理 | `feat` | — | 重点测 GR-016 |
| 11 | 前端：角色、Fork、共享资源、通知、活动、用量 | `feat` | 2~10 | 建议按后端进度分批合入 |
| 12 | 协作场景演示脚本 | `chore` | 11 | 验收用 |

## 风险与需要确认的事

| 风险 | 处理方式 |
| :--- | :--- |
| Shared Resource 的存储路径与集群共享存储（`/public`）如何对应还不确定 | 先用平台存储抽象，挂载方式由 RuntimeBackend 决定；实际路径策略需要向平台方确认，**不要写成固定结论** |
| 通知的产生点分散在多个 service，容易变成到处 `create_notification` | 统一走 `NotificationPublisher` 端口，产生点集中在用例层，不下沉到仓储 |
| 活动记录与管理审计容易混为一谈 | 活动面向 Workspace / Project 对象（§2.10 D），审计面向管理操作（§2.12 E）。M2 只做活动 |
| 加角色会波及所有已有权限判断点 | 先做 Issue 1 的重构，把判断从 `role is OWNER` 换成 `access.can(Capability.X)` |
| 协作会明显提高并发度：多人同时改同一个 Project、同时邀请同一个人 | 写入路径按 [ADR-0007](../decisions/0007-submission-correctness-and-observability.md) 的三问检查：有没有先读后写、有没有唯一约束兜底、有没有外部副作用 |
| 接口限流仍未做，协作场景下被刷的面更大 | 单实例可在进程内做，多实例需要共享状态；M2 期间如果要对外试用，这条要提前决定 |
| Fork 跨 Workspace 时的存储归属 | 内容寻址 blob 天然可共享，但配额记账要归到目标 Workspace（GR-002：归属与记账相互独立） |

## 与 M3 的边界

M3（Competition MVP）会在 M2 之上加 Course Profile 与 Assignment / Submission。
M2 必须把这三件事做扎实，否则 M3 会返工：

```text
角色与权限     → Assignment 的教师 / 助教 / 学生角色直接建在它上面
Fork           → 学生领取作业就是「从 Assignment 起始版本 Fork 到个人空间」
活动与通知     → 作业发布、提交、截止提醒都要用它
```
