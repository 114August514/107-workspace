# 产品设计

## 一. 顶级结构

```text
107 Workspace
│
├── 1. 用户、个人入口与全局导航
├── 2. User Group、成员与权限
├── 3. Project 与项目文件
├── 4. 模板、Fork 与项目复用
├── 5. 运行环境
├── 6. 共享资源与数据
├── 7. 算力与调度配置
├── 8. Run 生命周期与计算执行
├── 9. 日志、运行产物与复现信息
├── 10. 通知与活动
├── 11. 垂直场景 Profile
└── 12. 平台管理与运维
```

---

## 二. 产品能力细化

### 2.0 阶段标记

```text
[Core]
构成 107 Workspace 产品身份的基础能力。
后续 MVP 会从 Core 中进一步裁剪，并不代表 Core 必须一次全部实现。

[V1]
核心工作流稳定后，首批扩展能力。

[V2]
面向成熟协作、教学、数据管理和算力治理的增强能力。

[Future]
长期规划，当前只预留产品方向。
```

### 2.1 用户、个人入口与全局导航

``` text
用户、个人入口与全局导航
│
├── A. 个人入口
│   ├── [Core] 登录并识别当前用户
│   ├── [Core] 查看个人基本信息
│   ├── [Core] 查看自己拥有和参与的 User Group
│   ├── [Core] 查看自己拥有的 Project、Environment 和 Shared Resource
│   ├── [Core] 查看最近使用的 User Group 和 Project
│   ├── [Core] 查看最近发起的 Run
│   └── [Core] 从个人首页快速进入 Project 或 Run
│
├── B. 全局导航
│   ├── [V1] 搜索 User Group、Project 和 Run
│   ├── [V1] 在多个 User Group 和个人 Project 间切换
│   ├── [V1] 按名称、状态和时间筛选
│   ├── [V1] 置顶常用 User Group 和 Project
│   ├── [V1] 查看个人最近活动
│   ├── [V1] 查看等待处理的 User Group 邀请或其他事务
│   └── [V1] 对接学校统一身份认证
│
├── C. 个人执行上下文与算力权益
│   ├── [Core] 查看自己的 Resource Entitlement 和可用 Compute Plan
│   ├── [Core] 查看自己的算力使用权限
│   ├── [Core] 查看自己的 Variable
│   ├── [Core] 创建、修改和删除自己的 Variable
│   ├── [Core] 查看和管理自己的 Secret（不展示 Secret 明文）
│   ├── [V1] 提交 Entitlement Request
│   ├── [V1] 查看权益申请状态和历史
│   ├── [V1] 申请续期或调整权益
│   └── [V1] 主动释放不再需要的权益
│
├── [V2] 自定义个人首页
├── [V2] 保存常用筛选条件
├── [V2] 个人算力和存储使用概览
│
└── [Future] 个性化工作建议与快捷操作
```

### 2.2 User Group、成员与权限

User Group 是平台中的用户协作组织。User 可通过独立 Membership 加入多个 User Group。跨 Owner 使用资产需要显式 USE Grant。

当前治理角色采用 Owner / Admin / Member 三级模型。所有有效成员均可查看成员列表；Owner 可以邀请普通 Member、移除 Member 或 Admin，并可在 Member 与 Admin 之间显式变更角色；Admin 只能邀请普通 Member、移除普通 Member，不能变更任何成员角色或移除 Admin / Owner；Member 不具有成员治理权限。普通邀请只创建 Member，Owner 只能通过所有权转移用例产生或取消，不能通过普通角色变更完成。

```text
User Group、成员与共享资产
│
├── A. User Group 基本能力
│   ├── [Core] 创建 User Group
│   ├── [Core] 查看 User Group 基本信息
│   ├── [Core] 修改 User Group 名称和说明
│   ├── [Core] 查看 User Group 创建人和创建时间
│   ├── [Core] 查看当前用户在 User Group 中的 Membership Role
│   ├── [Core] 查看 User Group 拥有的 Project、Environment 和 Shared Resource
│   ├── [Core] 查看 User Group 概览和当前状态
│   ├── [V1] 设置图标和展示信息
│   ├── [V1] 归档与恢复 User Group
│   └── [Future] 设置标签并按标签或状态筛选
│
├── B. Membership 与 Role
│   ├── [Core] 查看成员列表
│   ├── [Core] 邀请成员并由受邀者确认或拒绝
│   ├── [Core] 移除成员或由成员主动退出
│   ├── [Core] 查看成员角色和状态
│   ├── [Core] Owner / Member 基础角色
│   ├── [Core] 转让 User Group 所有权
│   ├── [V1] Admin 扩展角色
│   ├── [V1] 修改成员角色
│   ├── [V2] 自定义角色
│   ├── [V2] 批量选择成员并授权
│   └── [Future] 外部协作者
│
└── C. User Group 共享资产与配置
    ├── [Core] 查看 User Group 拥有的 Environment 和 Shared Resource
    ├── [Core] 使用 User Group 拥有的 Environment 和 Shared Resource 创建 Run
    ├── [Core] 查看和管理 User Group 的 Variable
    ├── [Core] 查看和管理 User Group 的 Secret（不展示 Secret 明文）
    └── [V1] 为其他 User 或 User Group 建立本组资产的 USE Grant
```

### 2.3 Project 与项目文件

Project 是由 User 或 User Group 拥有的可版本化、可运行计算项目。每个 Run 都必须由具体 User 发起。

Project 具有可见性（Visibility）属性：仅成员可见（OWNER_SCOPE）或平台公开（PUBLIC）两种状态。Visibility 控制 Project 元数据与 Project Version 的发现和读取，以及基于可读取 Version 的 Fork 资格；操作权限不受影响，仍由 Ownership 与 Membership 决定。

```text
Project 与项目文件
│
├── A. Project 基本管理
│   ├── [Core] 以 User 或 User Group 作为 Owner 创建 Project
│   ├── [Core] 查看 Project 基本信息
│   ├── [Core] 查看 Project Visibility
│   ├── [Core] 设置 Project Visibility
│   ├── [Core] 修改 Project 名称和说明
│   ├── [Core] 查看 Project 最近更新时间
│   ├── [Core] 查看 Project 当前版本状态
│   ├── [Core] 查看 Project 的 Run 历史入口
│   │
│   ├── [V1] 归档或恢复 Project
│   ├── [V1] 设置 Project 图标和展示信息
│   ├── [V1] 搜索并浏览公开（PUBLIC）Project 的元数据与 Project Version
│   ├── [V2] 设置 Project 标签和分类
│   └── [Future] 在 User 与 User Group 所有权边界间显式转移 Project
│
├── B. 项目文件浏览与管理
│   ├── [Core] 查看文件和目录列表
│   ├── [Core] 查看文件大小、类型和修改时间
│   ├── [Core] 预览文本文件
│   ├── [Core] 下载单个文件
│   ├── [Core] 上传单个或多个文件
│   ├── [Core] 上传项目压缩包
│   ├── [Core] 查看文件上传进度
│   ├── [Core] 创建文件和目录
│   ├── [Core] 重命名文件和目录
│   ├── [Core] 移动文件和目录
│   ├── [Core] 复制文件和目录
│   ├── [Core] 删除文件和目录
│   │
│   ├── [V1] 在线编辑文本文件
│   ├── [V1] 批量选择和操作文件
│   ├── [V1] 按名称搜索文件和目录
│   ├── [V1] 预览 Markdown、图片和常见配置文件
│   ├── [V1] 导出完整 Project 压缩包
│   ├── [V1] 大文件分块上传
│   ├── [V1] 上传失败后继续传输
│   │
│   ├── [V2] 搜索文本文件内容
│   └── [V2] 查看文件级修改历史
│
├── C. 版本管理与 Git 式协作
│   ├── [Core] 查看当前未保存的文件变更
│   ├── [Core] 查看文件变更内容
│   ├── [Core] 放弃指定文件的未保存变更
│   ├── [Core] 保存当前 Project 版本
│   ├── [Core] 为版本填写说明
│   ├── [Core] 查看 Project 版本历史
│   ├── [Core] 查看版本创建人和创建时间
│   ├── [Core] 查看两个版本之间的差异
│   ├── [Core] 恢复到历史版本
│   ├── [Core] 从确定版本发起 Run
│   ├── [Core] 查看历史 Run 对应的 Project 版本
│   │
│   ├── [V1] 查看分支列表
│   ├── [V1] 创建开发分支
│   ├── [V1] 切换开发分支
│   ├── [V1] 合并开发分支
│   ├── [V1] 查看基础合并冲突
│   ├── [V1] 处理基础合并冲突
│   ├── [V1] 查看成员提交和分支活动
│   ├── [V1] 通过 Git 协议访问 Project
│   │
│   ├── [V2] 创建 Merge Request
│   ├── [V2] 评审代码变更
│   ├── [V2] 评论代码变更
│   ├── [V2] 设置默认分支
│   ├── [V2] 设置受保护分支
│   ├── [V2] 配置分支合并权限
│   ├── [V2] 管理需要随 Project 版本化的大型文件
│   │
│   └── [Future] 完整代码托管与高级评审流程
│
├── D. 外部导入、远程仓库与同步
│   ├── [V1] 从外部 Git 仓库导入 Project
│   ├── [V1] 保留外部仓库的版本历史
│   ├── [V1] 为 Project 连接外部 Git 仓库
│   ├── [V1] 查看外部仓库连接状态
│   ├── [V1] 查看本地与远程仓库的差异状态
│   ├── [V1] 拉取外部仓库更新
│   ├── [V1] 将 Project 更新推送到外部仓库
│   ├── [V1] 查看最近一次拉取或推送结果
│   ├── [V1] 从科大云盘导入文件或目录
│   │
│   ├── [V2] 管理多个外部 Git 仓库
│   ├── [V2] 配置分支同步关系
│   ├── [V2] 通过 CLI 增量同步本地目录
│   ├── [V2] 将项目文件导出到科大云盘
│   ├── [V2] 处理外部仓库同步冲突
│   │
│   └── [Future] 与外部代码平台持续双向同步
│
├── E. 开发工具入口
│   ├── [V1] 从 Project 打开 Shell
│   ├── [V1] 从 Project 打开远程 VS Code
│   ├── [V1] 打开开发工具时进入对应 Project
│   ├── [V1] 查看可用开发入口
│   │
│   ├── [V2] 通过本地开发工具连接 Project
│   └── [Future] 浏览器内完整开发环境
│
└── F. Project 运行方案与配置管理
    ├── [Core] 配置默认工作目录和执行命令
    ├── [Core] 查看运行方案的环境、共享资源和算力配置
    ├── [Core] 设置 Project 默认运行方案
    ├── [Core] 查看和管理 Project Variable
    ├── [Core] 查看和管理 Project Secret（不展示 Secret 明文）
    │
    ├── [V1] 创建和保存多个运行方案
    ├── [V1] 复制、修改和删除运行方案
    └── [V1] 设置运行方案名称和说明
```

### 2.4 模板、Fork 与项目复用

本方向负责从已有 Project 的确定版本创建新 Project，以及将 Project Version 发布为可发现、可复用的模板入口。

```text
Project 派生、模板发布与复用
│
├── A. Project 派生创建
│   ├── [Core] 从按 Project Visibility 可读取的已有 Project 的确定 Project Version 创建新 Project
│   ├── [Core] 选择来源 Project Version
│   ├── [Core] 查看来源 Project Version 的文件；仅在具有相应操作权限时查看来源 Run Configuration 概览
│   ├── [Core] 选择目标 Owner（User 或 User Group）
│   ├── [Core] 设置新 Project 名称和说明
│   ├── [Core] 查看目标 Owner 下的创建权限和资源引用可用性检查结果
│   ├── [Core] 创建派生 Project
│   └── [Core] 查看派生操作结果
│
├── B. 派生来源追踪
│   ├── [Core] 查看派生 Project 的来源 Project
│   ├── [Core] 查看派生 Project 的来源 Project Version
│   ├── [Core] 从来源信息进入原 Project
│   │
│   ├── [V2] 查看来源 Project 是否产生新版本
│   ├── [V2] 比较当前 Project 与来源版本
│   ├── [V2] 比较当前 Project 与来源的新版本
│   ├── [V2] 从来源的新版本创建 Project
│   │
│   └── [Future] 将来源版本的部分更新合并到当前 Project
│
├── C. 模板发布与管理
│   ├── [V1] 以 User 或 User Group 作为 Owner 创建 Template
│   ├── [V1] 设置模板名称、简介、使用说明、分类和标签
│   ├── [V1] 设置 Template Visibility
│   ├── [V1] 从同一 Owner 的 Project Version 发布 Template Revision
│   ├── [V1] 查看 Template Revision 的文件清单、来源记录和修订历史
│   ├── [V1] 设置当前推荐修订
│   ├── [V1] 查看当前 Owner 拥有的 Template
│   ├── [V1] 修改 Template 展示信息
│   ├── [V1] 弃用 Template
│   ├── [V1] 取消发布 Template
│   └── [V1] 删除 Template
│
├── D. 模板发现与使用
│   ├── [V1] 浏览当前用户可读取的 Template
│   ├── [V1] 搜索 Template
│   ├── [V1] 按分类和标签筛选 Template
│   ├── [V1] 查看 Template 详情和可用 Revision
│   ├── [V1] 查看 Template Revision 的文件概览和来源记录
│   ├── [V1] 进入有权读取的 Source Project Version
│   ├── [V1] 选择用于创建 Project 的 Template Revision
│   ├── [V1] 选择目标 Owner（User 或 User Group）
│   └── [V1] 从 Template Revision 创建独立 Project
│
└── E. 模板库治理
    ├── [V1] 发布 Owner 范围内可见的模板
    │
    ├── [V2] 发布平台范围内可见的模板
    ├── [V2] 查看模板使用次数
    ├── [V2] 查看由模板创建的 Project 数量
    ├── [V2] 查看模板最近使用情况
    ├── [V2] 设置推荐或精选模板
    │
    └── [Future] 模板评价、推荐与社区分享
```

### 2.5 运行环境

运行环境是由 User 或 User Group 拥有、供 Project 执行代码时复用的独立资产。Run Configuration 与 Run Snapshot 均引用确定的 Environment Version。

Environment Version 只允许两种显式 runtime kind：`modules` 与 `apptainer_sif`。
`modules` 固定使用 107 cluster profile、Environment Modules、`purge_then_ordered_load_v1`
并按用户选择顺序加载平台精确 allowlist；不接受任意 setup shell 或用户 modulefile。
`apptainer_sif` 固定记录 CAS 中精确 SIF 字节的 SHA-256、大小、locator、来源、x86_64
架构、`apptainer/1.4.5` launcher 与固定 exec policy。发布用真实 Apptainer CLI 验证，并从
`inspect --json` 的标准 build-arch label 读取实际 SIF 架构；只把 `amd64` 与 `x86_64`
归一为固定 `x86_64`，元数据缺失、格式错误、其他架构或 CLI 不存在时均失败，不降级。

发布由持久 Attempt 驱动，状态为 `pending -> processing -> succeeded|failed`。成功原子创建
一个不可变 Version，失败不创建 Version并保存原因和证据。不可变定义/验证证据与可变
`available|unavailable|deprecated` 状态分离。Run Snapshot 冻结精确 Version ID、definition
hash 与 execution spec；执行前按当前 User、Project Owner、USE Grant 和 availability 重检，
不回退到其他版本。当前处理循环是单 API 实例能力，不是多副本生产 Worker。真实 Apptainer
CLI 成功发布证据仍由 #46 负责；#7 只负责下游 Workspace 身份、共享挂载、独立 Worker 与
Slurm REST、凭据和执行接缝。

```text
运行环境
│
├── A. 环境发现与查看
│   ├── [Core] 浏览 Owner 范围内或经 USE Grant 可使用的运行环境
│   ├── [Core] 查看运行环境详情、Owner 和可用版本
│   ├── [V1] 搜索和筛选当前可发现的运行环境
│   ├── [V1] 查看环境版本更新说明
│   └── [Future] 根据 Project 推荐运行环境版本
│
├── B. User Group 默认 Environment Version
│   ├── [Core] 查看 User Group 默认 Environment Version
│   ├── [Core] 设置或修改可用的默认 Environment Version
│   ├── [V1] 查看修改默认版本的影响范围
│   └── [V1] 查看默认版本变更历史
│
├── C. Run Configuration 环境配置
│   ├── [Core] 查看 Run Configuration 引用的 Environment Version
│   ├── [Core] 选择并保存确定的 Environment Version
│   ├── [Core] 在发起 Run 前确认版本、使用资格和兼容性
│   ├── [V1] 在编辑配置时解析默认或推荐版本
│   ├── [V1] 查看环境不可用或不兼容的原因
│   └── [V2] 保存多个环境配置预设
│
├── D. 环境资产与版本管理
│   ├── [V1] 创建和维护由 User 或 User Group 拥有的 Environment
│   ├── [V1] 发布不可变 Environment Version
│   ├── [V1] 查看 Environment Version、构建与校验结果、日志、产物摘要和来源信息
│   ├── [V1] 弃用 Environment Version，归档或恢复 Environment
│   ├── [V1] 转移 Environment Ownership
│   ├── [V2] 导入和导出环境定义
│   ├── [V2] 比较 Environment Version 差异
│   └── [Future] 根据 Project 依赖自动创建环境
│
└── E. 环境共享与使用管理
    ├── [V1] 查看环境 Owner 范围和 USE Grant
    ├── [V1] 显式授权其他 User Group 或 User 使用环境
    ├── [V1] 查看、管理和撤销 USE Grant
    ├── [V1] 查看引用确定环境版本的 Run Configuration 和近期 Run
    ├── [V1] 查看环境与版本的可用状态和使用限制
    ├── [V2] 设置环境授权有效期
    ├── [V2] 查看环境使用统计
    └── [V2] 查看兼容性和安全检查结果
```

### 2.6 共享资源与数据

Shared Resource 是由 User 或 User Group 拥有、独立于 Project 的可版本化内容资产。Run Configuration 通过 Input Binding 引用确定的 Shared Resource Version。

```text
共享资源与数据
│
├── A. 资源发现与查看
│   ├── [Core] 浏览 Owner 范围内或经 USE Grant 可使用的共享资源
│   ├── [Core] 查看共享资源详情、Owner、使用说明和可用版本
│   ├── [Core] 查看当前 User 对 Shared Resource 的可用状态
│   ├── [V1] 搜索和筛选当前可发现的共享资源
│   ├── [V1] 预览资源目录、样例或结构信息
│   └── [Future] 根据 Project 推荐共享资源版本
│
├── B. Run Configuration 输入资源配置
│   ├── [Core] 查看 Project 下 Run Configuration 引用的共享资源
│   ├── [Core] 在 Run Configuration 中配置 Shared Resource Version 与访问位置
│   ├── [Core] 更换或解除 Input Binding
│   └── [V1] 查看创建 Run 时输入资源校验失败的原因和处理方式
│
├── C. 共享资源与版本管理
│   ├── [Core] 创建和维护由 User 或 User Group 拥有的 Shared Resource
│   ├── [Core] 上传或导入资源内容
│   ├── [Core] 发布不可变 Shared Resource Version
│   ├── [Core] 查看 Shared Resource Version 的校验结果和日志，以及内容摘要、结构和来源信息
│   ├── [V1] 设置推荐版本，填写和查看版本更新说明
│   ├── [V1] 将 Project 文件、目录或 Run Artifact 发布为 Shared Resource 或新 Version
│   ├── [V1] 弃用 Shared Resource Version，归档或恢复 Shared Resource
│   ├── [V1] 转移 Shared Resource Ownership
│   ├── [V2] 比较 Shared Resource Version 内容
│   └── [Future] 与外部数据源保持版本同步
│
├── D. 资源共享与权限管理
│   ├── [Core] 查看资源 Owner 范围和 USE Grant
│   ├── [V1] 将共享资源显式授权给指定 User Group 或 User 使用
│   ├── [V1] 查看、管理和撤销 USE Grant
│   ├── [V2] 设置资源授权有效期
│   └── [V2] 管理资源下载和导出策略
│
└── E. 引用与使用追踪
    ├── [V1] 查看引用指定 Shared Resource Version 的 Run Configuration
    ├── [V1] 查看使用指定资源版本的近期 Run
    ├── [V1] 查看版本弃用、资产归档或撤权的影响
    └── [V2] 查看共享资源使用统计
```

### 2.7 算力与调度配置

每次 Run 使用发起 User 的 Resource Entitlement 判断 Compute Plan 资格。Project 保存默认资源配置，Run 固定本次资源请求，底层调度系统负责真正的排队与分配；Project Owner 不提供或转移算力权益。

```text
算力与调度配置
│
├── A. Project 算力配置
│   ├── [Core] 查看当前 User 可使用的算力方案
│   ├── [Core] 查看算力方案的资源内容和限制
│   ├── [Core] 在发起 User 可用的算力方案之间切换
│   └── [Core] 查看方案对当前 User 不可用的原因
│
├── B. 高级资源与调度配置
│   ├── [V1] 切换到高级配置模式
│   ├── [V1] 配置节点数量、CPU、内存、GPU 和最长运行时间
│   ├── [V1] 选择当前 User 可用的调度账户、分区和 QoS
│   ├── [V1] 将部分参数保留为自动选择
│   ├── [V1] 查看配置对应的资源总量
│   ├── [V1] 将高级配置保存到 Project 运行方案
│   ├── [V2] 从超出当前 User 权益的资源请求发起 Entitlement Request
│   └── [V2] 在权益获批后恢复原资源配置
│
└── C. 调度请求解析与校验
    ├── [Core] 查看本次 Run 最终的资源请求
    ├── [Core] 检查资源请求是否符合发起 User 的 Resource Entitlement
    ├── [Core] 检查资源请求是否符合平台限制
    ├── [Core] 检查资源请求与运行环境是否兼容
    ├── [Core] 查看配置不可用或超出限制的原因
    │
    ├── [V1] 检查账户、分区和 QoS 组合是否有效
    ├── [V1] 查看平台解析后的调度配置
    ├── [V1] 将高级配置恢复为自动配置
    │
    ├── [V2] 选择节点特征或特定硬件能力
    ├── [V2] 使用资源预约
    ├── [V2] 配置多节点和分布式任务
    └── [Future] 根据权益和负载推荐执行集群
```

### 2.8 Run 生命周期与计算执行

Run 由具体 User 在 Project 下发起。平台分别校验 Project 操作权限、资产使用资格和发起 User 的算力资格，并将确定的执行配置固定为 Run Snapshot 后提交执行。

```text
Run 生命周期与计算执行
│
├── A. Run 创建与提交
│   ├── [Core] 从有权创建 Run 的 Project 发起 Run
│   ├── [Core] 选择或使用 Project 默认运行方案
│   ├── [Core] 查看并调整本次 Run 的工作目录和执行命令
│   ├── [Core] 查看 Project、资产和算力资格的校验结果
│   ├── [Core] 确认本次 Run 的代码快照和完整执行配置
│   └── [Core] 提交 Run
│       │
│       ├── [V1] 设置 Run 名称和备注
│       └── [V1] 查看生成的调度请求和作业脚本
│
├── B. Run 状态与任务控制
│   ├── [Core] 查看 Run 当前状态和执行时间线
│   ├── [Core] 查看排队时长和运行时长
│   ├── [Core] 查看等待、失败、超时或终止原因
│   ├── [Core] 取消等待中或运行中的 Run
│   └── [Core] 查看 Run 最终结果
│       │
│       └── [V1] 查看底层调度任务信息和详细状态
│
├── C. 重新运行与派生执行
│   ├── [Core] 在所记录的代码、环境和输入内容仍可用时，基于历史 Run 的确定配置重新运行
│   ├── [Core] 基于历史 Run 调整配置后创建新 Run
│   ├── [Core] 从提交失败或运行失败的 Run 重新尝试
│   └── [Core] 查看新 Run 与来源 Run 的关系
│       │
│       ├── [V2] 配置自动重试条件和次数
│       └── [Future] 从检查点继续运行
│
├── D. Run 历史与执行快照
│   ├── [Core] 查看 Project 的 Run 历史
│   ├── [Core] 查看 Run 状态、来源和关键时间
│   ├── [Core] 查看执行配置摘要
│   ├── [Core] 查看 Run 记录的 Project Version 身份及其当前可用状态
│   │
│   ├── [V1] 搜索和筛选 Run
│   ├── [V1] 为 Run 添加标签和备注
│   └── [V2] 比较不同 Run 的执行配置
│
└── E. 批量与关联执行
    ├── [V2] 使用多组参数批量创建 Run
    ├── [V2] 配置 Run 之间的依赖关系
    └── [Future] 编排多阶段计算流程
```

#### Run 创建时固定的内容

```text
Run Snapshot
├── 来源 Project
├── Project Version
├── 来源运行方案
├── 工作目录
├── 最终执行命令
├── 环境版本
├── Shared Resource Version 与访问位置
├── CPU、内存、GPU、节点数和时限
├── Account、Partition、QoS 等最终调度配置
└── 创建时间
```

### 2.9 日志、运行产物与复现信息

本节呈现 Run 执行过程中产生的信息和结果，并保存用于解释、比较和判断是否能够再次执行该 Run 的复现信息。

```text
日志、运行产物与复现信息
│
├── A. 运行日志
│   ├── [Core] 查看 Run 的实时输出
│   ├── [Core] 分别查看标准输出和标准错误
│   ├── [Core] 查看平台产生的执行事件和错误信息
│   ├── [Core] 在 Run 结束后查看完整日志
│   ├── [Core] 下载 Run 日志
│   │
│   ├── [V1] 搜索和筛选日志内容
│   ├── [V1] 从日志错误进入相关排障信息
│   ├── [V1] 查看日志是否被截断或不完整
│   └── [V2] 自动识别常见错误并提供诊断建议
│
├── B. Artifact 收集与查看
│   ├── [Core] 为运行方案配置需要收集的输出路径
│   ├── [Core] 在 Run 结束后收集指定输出为 Artifact
│   ├── [Core] 查看 Run 产生的 Artifact
│   ├── [Core] 查看 Artifact 基本信息和目录结构
│   ├── [Core] 下载单个 Artifact 文件
│   ├── [Core] 下载完整 Artifact
│   │
│   ├── [V1] 预览文本、图片、表格和常见结果文件
│   ├── [V1] 从仍被保留的 Run 工作目录创建新的 Artifact 快照
│   ├── [V1] 为 Artifact 设置名称和说明
│   ├── [V1] 导出多个 Artifact
│   └── [V2] 比较不同 Run 的 Artifact
│
├── C. 结果复用与发布
│   ├── [V1] 将 Artifact 复制到 Project
│   ├── [V1] 将 Artifact 用作新 Run 的输入
│   ├── [V1] 从 Artifact 发起共享资源发布
│   │
│   ├── [V2] 生成 Artifact 的临时分享入口
│   └── [V2] 查看 Artifact 的引用和使用情况
│
├── D. 指标与结果比较
│   ├── [V1] 查看 Run 上报的结构化指标
│   ├── [V1] 查看指标随执行过程的变化
│   ├── [V1] 查看 Run 的关键结果摘要
│   │
│   ├── [V2] 比较多个 Run 的指标
│   ├── [V2] 比较不同代码、环境和算力配置下的结果
│   └── [Future] 创建实验分析看板
│
└── E. 复现信息
    ├── [Core] 查看 Run 的完整执行快照
    ├── [Core] 查看 Run Snapshot 记录的 Project Version、命令和工作目录
    ├── [Core] 查看 Run 使用的环境和共享资源版本
    ├── [Core] 查看 Run 使用的算力与调度配置
    ├── [Core] 查看 Run 的退出状态和关键执行信息
    │
    ├── [V1] 导出 Run 复现信息清单
    ├── [V1] 查看复现所需依赖当前是否仍然可用
    └── [Future] 导出可移植的完整复现包
```

日志、Artifact 内容和 Run 工作目录会按各自的保留期限清理。到期后，这些内容将无法查看或下载，但 Run Snapshot 仍按 Run 的生命周期保留。

### 2.10 通知与活动

Activity 记录对象上已经发生了什么；Notification 将需要关注或处理的信息发送给特定 User。

```text
通知与活动
│
├── A. 通知中心
│   ├── [Core] 查看与当前用户相关的通知
│   ├── [Core] 查看未读通知数量
│   ├── [Core] 查看通知类型、时间和关联对象（如有）
│   ├── [Core] 从通知进入仍可访问的关联对象
│   ├── [Core] 将通知标记为已读或未读
│   ├── [Core] 批量标记通知为已读
│   │
│   ├── [V1] 按类型和时间筛选通知
│   ├── [V1] 搜索通知
│   └── [V1] 归档或删除历史通知
│
├── B. 重要事件通知
│   ├── [Core] 接收自己发起的 Run 结束或异常通知
│   ├── [Core] 接收 User Group 的 Membership 或 Role 变更通知
│   ├── [Core] 接收 Project 所用 Environment 或 Shared Resource 的不可用通知
│   ├── [Core] 接收平台维护和服务异常通知
│   │
│   ├── [V1] 接收 Run 开始运行通知
│   ├── [V1] 接收 Shared Resource Version 弃用、Shared Resource 归档或 USE Grant 撤销通知
│   ├── [V1] 接收 Environment Version 弃用或 Environment 可用性变化通知
│   └── [V1] 接收配额接近上限和生命周期提醒
│
├── C. 通知订阅、偏好与送达
│   ├── [Core] 在平台内接收通知
│   ├── [Core] 按通知类别启用或关闭非强制通知
│   ├── [Core] 查看不可关闭的重要系统通知
│   │
│   ├── [V1] 通过邮件接收重要通知
│   ├── [V1] 分别配置站内和邮件通知偏好
│   ├── [V1] 设置免打扰时段
│   ├── [V1] 接收每日或每周通知摘要
│   ├── [V2] 订阅当前有权查看对象的重要变化
│   ├── [V2] 按订阅对象和通知类别配置偏好
│   └── [Future] 接入更多外部消息渠道
│
├── D. 对象活动
│   ├── [Core] 查看 Project 的近期活动
│   ├── [Core] 查看活动的操作者、动作、作用对象和发生时间
│   │
│   ├── [V1] 查看 Environment 的近期活动
│   ├── [V1] 查看 Shared Resource 的近期活动
│   └── [V1] 按操作者、动作和时间筛选对象活动
│
└── E. 活动汇总
    ├── [Core] 查看 User Group 的活动汇总
    ├── [Core] 汇总 User Group 本身、Membership，以及该组当前拥有的 Project 相关活动
    │
    ├── [V1] 将该组当前拥有的 Environment 与 Shared Resource 相关活动纳入汇总
    ├── [V1] 查看与自己明确相关的活动
    └── [V1] 按操作者、对象类型和时间筛选汇总活动
```

### 2.11 垂直场景 Profile

Profile 将既有平台能力的默认配置、导航和工作流程组织为可复用的场景扩展。

```text
垂直场景 Profile
│
├── A. Profile 资产与版本
│   ├── [V1] 查看当前 Owner 拥有的 Profile、说明和版本信息
│   ├── [V1] 以 User 或 User Group 作为 Owner 创建和维护 Profile
│   ├── [V1] 设置 Profile Visibility
│   ├── [V1] 发布不可变 Profile Version
│   └── [V1] 查看 Profile 的版本历史和更新说明
│
└── B. User Group 场景配置
    ├── [V1] 查看 Profile Instance 引用的确定 Profile Version 和当前配置
    ├── [V1] 查看和修改 Profile Instance 的场景配置
    ├── [V1] 配置 Environment Version 和 Shared Resource Version 的默认或推荐引用
    ├── [V1] 基于当前 User Group 可读取的确定 Profile Version 启用 Profile
    ├── [V1] 显式升级至当前 User Group 可读取的另一确定 Profile Version 并查看影响
    └── [V1] 停用或删除 Profile Instance 并查看影响
```

读取或启用 Profile 仅使其场景定义可用，不改变 Membership，也不授予所引用资源或配置的访问权、Resource Entitlement 或运行权限。

### 2.12 平台管理与运维

本节面向 Platform Admin，分别管理平台运行、算力基础设施、全局 Run、身份支持、存储限制、算力资格、全局策略以及故障与审计。

Platform Admin 只能查看平台支持与运维所需的身份状态、聚合用量和运行元数据；该身份不授予业务数据读取权。平台提供的 Environment 与 Shared Resource 仍由平台运营 User Group 中具有相应 Membership 的具体 User 按普通资产流程管理。

全局 Run 运维应使用独立的管理投影，仅提供筛选、定位、调度和干预所需的运行元数据，不包含业务内容或完整 Run 详情。

Resource Entitlement 只表示 User 对 Compute Plan 的算力使用资格；User Group 的存储容量限制是独立的平台配额，不属于 Resource Entitlement。Compute Plan 与底层集群、调度映射由 Platform 管理。

平台管理变更应在执行前显示可判定的影响范围，并记录操作者、时间、原因和结果。

```text
平台管理与运维
│
├── A. 平台运行概览
│   ├── [V1] 查看认证、调度、存储、Git、通知和监控等关键服务的可用状态
│   └── [V1] 查看算力与存储容量、排队中/运行中/异常 Run 以及当前告警摘要
│
├── B. Compute Plan 与集群接入
│   ├── [V1] 查看已接入集群、节点和分区的容量与运行状态
│   ├── [V1] 创建、调整和停用 Compute Plan，并维护其对集群、调度账户、分区和 QoS 的映射
│   └── [V1] 设置集群或分区的维护状态，并控制是否接收新的 Run
│
├── C. 全局 Run 运维
│   ├── [V1] 按运行状态、集群、分区、User 或 User Group 查看和筛选全平台 Run 与 Scheduler Job
│   ├── [V1] 查看 Run 与 Scheduler Job 的对应关系、资源请求、实际分配、排队原因和异常分类
│   └── [V1] 取消或终止需要管理员干预的 Run 或 Scheduler Job，并记录原因和结果
│
├── D. User 与 User Group 身份支持
│   ├── [V1] 搜索并查看 User、User Group 及其身份状态
│   └── [V1] 停用或恢复 User 的平台访问，并查看受影响范围
│
├── E. User Group 存储容量限制
│   ├── [V1] 查看 User Group 当前存储用量和容量限制
│   └── [V1] 配置 User Group 的存储容量限制
│
├── F. User 算力资格
│   ├── [V1] 查看 User 的 Entitlement Request 和当前 Resource Entitlement
│   └── [V1] 批准或拒绝 Entitlement Request；批准后创建、调整或延长该 User 的 Resource Entitlement
│
├── G. 全局策略与平台集成
│   ├── [V1] 查看和配置 Project Version、Environment Version、Shared Resource Version、Run 与 Run Snapshot、Log、Artifact 内容及 Run 工作目录的全局保留策略
│   └── [V1] 查看认证、Slurm、存储、Git、通知和监控集成的配置状态与最近错误
│
└── H. 告警、故障与平台审计
    ├── [V1] 查看和处理告警，并创建、更新或关闭平台故障事件
    ├── [V1] 查看故障影响的集群、Run、User Group 和 User
    ├── [V1] 发布、更新和撤回维护或故障公告
    └── [V1] 查看和筛选平台管理变更记录
```

---

## 三. 领域模型与产品规则

### 3.0 本章目的

本章用于定义 107 Workspace 的领域语言、核心对象、对象关系、业务不变量、关键工作流和权限边界。

产品能力章节回答：

```text
用户可以做什么
```

本章回答：

```text
这些操作作用于什么对象
对象归属于谁
对象之间是什么关系
操作需要满足什么条件
操作完成后产生什么结果
权限、状态和生命周期如何变化
```

本章暂不规定：

```text
数据库表结构
ORM Entity
REST API 路径
Repository 接口
服务拆分方式
消息中间件
具体文件系统布局
```

这些内容在技术设计阶段确定。

---

### 3.1 统一领域语言

同一概念在产品文档、代码、接口和数据库中应使用一致名称。

#### 3.1.1 身份与空间

| 名称 | 定义 |
| :---- | :-- |
| User | 使用平台的自然人身份 |
| User Group | 平台中的用户协作组织 |
| Membership | 连接 User 与 User Group 的成员关系 |

本节统一采用以下授权术语；授权作用对象称为 Target，不使用含义过宽的 Resource：

| 名称 | 定义 |
| :---- | :-- |
| Grant | Grantor 向 Grantee 授予的跨 Owner 使用许可 |
| Grantor | 发出 Grant 的 User 或 User Group |
| Grantee | 获得 Grant 的 User 或 User Group |
| Target | Grant 的作用范围：`ALL`，或某个顶层 Environment / Shared Resource；不直接指向 Version |
| Action | Grant 中“允许做什么”的操作；当前只有 USE |

`Target = ALL` 只覆盖当前 Owner 为 Grantor 的资产，包括 Grantor 后续新建或取得的资产。具体执行 Grant 操作的 User 只作为操作者记录，不改变 Grantor、Grantee 或 Target 的语义。

`Membership` 的结构如下：

```text
Membership
├── User
├── User Group
├── Role
└── Status
```

同一 User 可以在多个 User Group 中分别建立 Membership；每个 Membership 只作用于其连接的确定 User Group。

Profile 不改变 User 与 User Group 的基础身份关系。Course Profile 及课程专用领域对象尚未进入正式设计，统一记录在 `docs/product/deferred.md`。

#### 3.1.2 Project 与版本

| 中文名称 | 英文名称 | 定义 |
| :----- | :---- | :--- |
| Project | Project | 由 User 或 User Group 拥有的可编辑、可版本化计算项目；实际 Run 必须由 User 发起 |
| 项目可见性 | Project Visibility | 控制谁能找到并查看 Project 及其不可变版本：OWNER_SCOPE 仅 Owner 范围内可见，PUBLIC 对所有已认证 User 可见 |
| Project 当前状态 | Project Working State | Project 当前可编辑的文件和目录状态 |
| Project 版本 | Project Version | Project 在某个时刻正式保存的不可变内容快照 |
| 分支 | Project Branch | 指向某个 Project Version 的可变开发引用 |
| 运行方案 | Run Configuration | Project 下可编辑、可命名、可复用的执行配置 |
| 派生关系 | Fork Relation | 新 Project 与来源 Project Version 之间的来源记录 |
| 模板 | Template | 由 User 或 User Group 拥有，用于基于预先确定的项目内容创建独立 Project 的可复用模板 |
| 模板可见性 | Template Visibility | 控制 Template 及其 Revision 的发现和读取范围：OWNER_SCOPE 仅 Owner 范围内可见，PUBLIC 对所有已认证 User 可见 |
| 模板修订 | Template Revision | Template 发布形成的不可变内容版本，包含确定文件清单和来源记录，用于创建独立 Project |

Template 是发布与目录对象，不具有独立代码仓库或 Project Working State，不是 Grant Target 或 Environment 一类的运行资产，也不产生持续权限关系。

#### 3.1.3 运行环境、内容资源与输入

| 中文名称 | 英文名称 | 定义 |
| :--- | :--- | :--- |
| 运行环境 | Environment | 由 User 或 User Group 拥有、可被多个 Project 选择和复用的独立运行基础 |
| 环境版本 | Environment Version | 环境构建和校验成功后发布的不可变版本 |
| 共享资源 | Shared Resource | 由 User 或 User Group 拥有、独立于 Project 的可版本化内容资产 |
| 共享资源版本 | Shared Resource Version | 资源内容校验通过后发布的不可变版本 |
| Artifact | Artifact | 某次 Run 产生并被保存的不可变结果 |
| 确定内容 | Content Version | 具有稳定内容身份、不会原地变化的文件、文件集合或目录快照 |
| 输入绑定 | Input Binding | 将一份确定内容绑定到 Run 中指定访问路径的关系 |
| 输入访问路径 | Input Access Path | 确定内容在 Run 执行环境中暴露的文件或目录路径 |

Environment 与 Shared Resource 是两类彼此独立的资产，只有通过各自类型的校验，才能发布不可变 Version。二者共用同一套 Ownership 与 USE Grant 模型，但产品不向用户提供统一的“通用资产”类型。发布 Version 只会形成不可变版本，不会自动公开资产或扩大访问范围。

运行环境与输入内容承担不同职责：

```text
Environment Version
→ 决定代码在什么软件和系统基础上运行

Input Binding
→ 决定 Run 可以读取哪些确定内容，以及通过什么路径读取
```

Shared Resource Version 和 Artifact 虽然具有不同的业务语义，但都可以向 Run 提供确定内容：

```text
Shared Resource Version
└── 提供被正式版本化和授权管理的确定内容

Artifact
└── 提供某次 Run 产生的确定结果内容

Shared Resource Version ──┐
                          ├── 提供 Content Version
Artifact ─────────────────┘
                                  ↓
                            Input Binding

Content Version 是对不可变文件或目录内容的统一抽象，不一定对应用户可直接管理的独立对象。
```

Input Binding 不需要针对不同来源设计不同结构。它统一引用一份确定内容，并指定该内容在 Run 中的访问路径：

```text
Input Binding
├── Source Content Version
├── 可选 Source Subpath
└── Input Access Path
```

例如：

```text
Input Binding
├── Source Content Version: dataset-v2
├── Source Subpath: train/
└── Input Access Path: /inputs/train
```

含义是：

```text
dataset-v2 中的 train/
        ↓
在 Run 中暴露为 /inputs/train
```

Input Binding 可以存在于两个位置：

```text
Run Configuration
→ 保存可编辑、可复用的输入配置

Run Snapshot
→ 保存创建 Run 时已经解析和固定的不可变输入记录
```

创建 Run 时，平台必须先确认发起 User 有权使用每项输入且相应内容可用，再将 Input Binding 解析为精确引用并写入 Run Snapshot。Snapshot 创建后，授权撤销或内容状态变化不得改变其中的引用。后续物化或重新执行时，如果该精确引用已经无权访问或内容不可用，操作必须失败，不得自动改用其他 Version 或其他内容。

所有通过 Input Binding 提供的内容仅能以只读方式供 Run 使用：

```text
确定内容
→ 只读提供给 Run

需要修改
→ 复制到 Run 工作目录或 Project 后再修改
```

#### 3.1.4 配置变量、Secret 与环境变量

| 中文名称 | 英文名称 | 定义 |
| :---- | :------ | :--- |
| 配置变量 | Variable | 由 User、User Group 或 Project 管理、可直接查看和引用的非敏感键值配置 |
| Secret | Secret | 由 User、User Group 或 Project 安全保存、用于存储 Token、密码和密钥等敏感信息的键值配置 |
| 环境变量 | Environment Variable | 由 Run Configuration 定义，并在 Run 执行时提供给用户程序的键值配置 |

Variable 和 Secret 分别属于一个 User、User Group 或 Project。Project 级值是本 Project 的本地配置；Project Owner 级值是该 Owner 下 Project 可复用的默认配置：

```text
User
├── Variables
└── Secrets

User Group
├── Variables
└── Secrets

Project
├── Variables
├── Secrets
└── Run Configuration
    └── Environment Variables
```

Run Configuration 使用与 GitHub Actions 类似的表达式引用 Variable 和 Secret。下面以 User Group-owned Project 为例：

```yaml
env:
  LOG_LEVEL: ${{ vars.LOG_LEVEL }}
  BATCH_SIZE: "32"
  HF_TOKEN: ${{ secrets.HF_TOKEN }}
  WANDB_PROJECT: ${{ user.vars.WANDB_PROJECT }}
  WANDB_API_KEY: ${{ user.secrets.WANDB_API_KEY }}
```

其中：

```text
Literal Value
→ 直接保存在 Run Configuration 中

${{ vars.LOG_LEVEL }} / ${{ secrets.HF_TOKEN }}
→ 先查找当前 Project
→ Project 中不存在同名项时，再查找其 Owner

${{ user.vars.NAME }} / ${{ user.secrets.WANDB_API_KEY }}
→ 仅引用 Initiated By User 的个人配置
→ 不参与标准引用的 Project > Project Owner 回退

env
→ 指定最终提供给程序的环境变量名称
```

标准引用只在 Project 中不存在同名项时回退到 Project Owner。已命中的项不可用或无权使用时不得继续回退；Project 与 Project Owner 都没有可用项时，引用未解析。显式 `user` 引用只查找 Initiated By User，缺失或无权使用时也不得回退。

Variable 和 Secret 的源名称不必与最终环境变量名称相同：

```yaml
env:
  TOKEN: ${{ secrets.HF_TOKEN }}
```

运行时等价于：

```bash
TOKEN=<HF_TOKEN 对应的秘密值>
```

用户程序只需要按照普通环境变量读取：

```python
import os

token = os.environ["TOKEN"]
```

创建和执行 Run 时：

```text
普通值和 Variable
→ 创建 Run 时解析并固定到 Run Snapshot

Secret
→ 创建 Run 时确定 exact Secret 引用
→ Run Snapshot 只保存该引用，不保存 Secret 明文
→ 执行 Run 时按当前有效授权安全取得当前值
```

Variable 和 Secret 应遵守以下规则：

```text
1. 非敏感配置使用 Variable，敏感信息使用 Secret。
2. ${{ vars.NAME }} 和 ${{ secrets.NAME }} 先在 Project scope 中查找，未找到时再在 Project Owner scope 中查找。Project Owner scope 只指该 Project 的直接 Owner：由 User 拥有时指该 User，由 User Group 拥有时指该 User Group。
3. ${{ user.vars.NAME }} 和 ${{ user.secrets.NAME }} 只在 Initiated By User 的个人 scope 中查找，不回退到 Project 或 Project Owner scope。
4. 创建 Run 时，平台必须确认所有 Variable 和 Secret 引用均已存在、当前可用，并且 Initiated By User 有权使用。任何引用无法解析时，Run 创建必须失败，不得将其替换为空字符串。
5. Project 文件和 Run Configuration 只能保存 Secret 引用，不得保存 Secret 明文。Secret 设置后不得通过页面或 API 回读其值；有权管理该 Secret 的 User 只能查看其元数据，或者执行创建、替换、轮换和删除操作。
6. 创建 Run 时，平台必须解析所有 Variable 引用，并将解析出的值写入 Run Snapshot。Variable 后续发生变化，不得影响已有 Run Snapshot。
7. Run Snapshot 只保存 Secret 的精确引用，不保存 Secret 值。执行 Run 时，平台必须重新确认该引用仍然有效、Initiated By User 仍有权使用，并读取其当前值。Run Snapshot、日志和页面均不得展示 Secret 明文。
8. Project Visibility 不得暴露任何 Project、Project Owner 或 User scope 下的 Variable、Secret，也不得暴露 Run Configuration。
9. Fork Project 或使用 Template 创建 Project 时，不得复制 Variable、Secret 的值或原有访问权。其中保留的 Run Configuration 引用表达式，必须在目标 Project、目标 Project Owner 和目标 Run 的 Initiated By User scope 中重新解析。
```

最终领域关系就是：

```text
User / User Group / Project
├── Variable
└── Secret

Run Configuration
└── Environment Variables
    ├── Literal Value
    ├── ${{ vars.NAME }} / ${{ secrets.NAME }}
    └── ${{ user.vars.NAME }} / ${{ user.secrets.NAME }}
        ↓ 创建 Run

Run Snapshot
├── 已固定的普通值和 Variable 值
└── exact Secret 引用
```

#### 3.1.5 算力、权益与调度

| 中文名称 | 英文名称 | 定义 |
| :------ | :----- | :--- |
| 算力方案 | Compute Plan | 平台面向用户提供的命名资源与运行限制组合 |
| 资源权益 | Resource Entitlement | User 获得的算力方案使用资格及其有效期限 |
| 权益申请 | Entitlement Request | User 请求开通、调整或延长算力资格的申请记录 |
| 算力请求 | Compute Request | Run Configuration 为一次运行声明的具体资源需求 |
| 已解析调度配置 | Resolved Scheduler Configuration | 创建 Run 时解析并固定的最终调度与资源参数 |
| 资源使用记录 | Resource Usage Record | Run 执行产生的资源分配、运行时长、运行状态及可观测使用情况 |

权益申请审核通过后，形成或更新 User 的资源权益：

```text
Entitlement Request
        ↓ 审核通过
Resource Entitlement
        ↓
User 可以使用相应的 Compute Plan
```

Run Configuration 选择算力方案，并声明本次运行的具体资源需求：

```text
Run Configuration
├── Compute Plan
└── Compute Request
    ├── CPU
    ├── Memory
    ├── GPU
    └── Time Limit
```

创建 Run 时，平台根据资源权益、算力方案、算力请求和调度映射，生成最终调度配置：

```text
Resource Entitlement
        +
Compute Plan
        +
Compute Request
        ↓ 平台解析
Resolved Scheduler Configuration
        ↓
提交并执行 Run
        ↓
Resource Usage Record
```

各概念分别回答：

```text
Resource Entitlement
→ User 有权使用哪些算力方案

Compute Plan
→ 平台向用户提供什么算力方案

Compute Request
→ 本次运行具体需要多少资源

Resolved Scheduler Configuration
→ 本次 Run 最终使用什么调度与资源参数

Resource Usage Record
→ 本次 Run 实际分配了什么资源、运行了多久
```

应遵守以下规则：

```text
1. User 只能使用其 Resource Entitlement 允许的 Compute Plan。

2. Compute Request 必须符合所选 Compute Plan 的资源范围和运行限制。

3. Resolved Scheduler Configuration 在创建 Run 时固定到 Run Snapshot；
   后续权益、算力方案或映射规则变化不得改变已有 Run。

4. Resource Usage Record 用于运行详情、故障定位和平台运维。

5. Entitlement Request 是申请记录；
   只有审核通过后形成的 Resource Entitlement 才代表有效使用资格。
```

底层实现不在本章涉及。

#### 3.1.6 Run 与执行过程

| 中文名称 | 英文名称 | 定义 |
| :------ | :----- | :--- |
| Run | Run | 由具体 User 在 Project 下基于确定版本和运行配置发起的一次独立执行实例 |
| Run 快照 | Run Snapshot | Run 创建时固定、用于执行并记录本次配置的不可变记录 |
| 调度任务 | Scheduler Job | Run 提交后由底层调度系统创建和执行的任务 |
| 日志 | Log | Run 执行过程中产生的标准输出、标准错误和平台执行事件 |
| Artifact 收集规则 | Artifact Collection Rule | 指定 Run 执行结束后，将哪些输出文件或目录保存为 Artifact 的配置 |
| 指标 | Metric | Run 可选上报的结构化数值结果或时间序列，用于结果展示和运行对比 |

Run Configuration 是 Project 下可编辑、可复用的运行方案，包括：

```text
Run Configuration
├── Working Directory
├── Command
├── Environment Version
├── Input Binding
├── Environment Variables
├── Compute Plan
├── Compute Request
└── Artifact Collection Rules
```

界面可以在用户编辑 Run Configuration 时，根据默认值、推荐值或别名帮助选择版本；保存 Run Configuration 前，平台必须将这些可变选择解析为具体的 Environment Version 和 Shared Resource Version。Run Configuration 和 Run Snapshot 只保存具体版本的精确引用。创建或执行 Run 时不得再次解析默认值、推荐值或别名，也不得自动切换到其他版本。

创建 Run 时，平台将当前 Project Version 与 Run Configuration 中的配置解析为确定内容，并生成 Run Snapshot：

```text
Project Version
        +
Run Configuration
        +
创建时校验与解析结果
        ↓
Run Snapshot
        ↓
Run
```

Run Configuration 与 Run Snapshot 包含相近的配置内容，但承担不同职责：

```text
Run Configuration
→ 描述以后准备怎样运行
→ 可以编辑和复用

Run Snapshot
→ 记录本次 Run 实际按照什么配置运行
→ 创建后不可修改
```

创建 Run 时，各项配置均固定成不变量，于是：

```text
Run Snapshot
=
Project Version
+
已解析并固定的 Run Configuration
+
Resolved Scheduler Configuration
```

Run 可以保留对来源 Run Configuration 的引用，但该引用不作为执行依据：

```text
Run
├── Source Run Configuration
│   └── 用于来源追踪和配置复用
│
└── Run Snapshot
    └── 用于实际执行、历史查看和复现信息展示
```

Run 创建后，包含来源信息、不可变执行快照和可变化的执行信息：

```text
Run
├── 来源信息
│   ├── Project
│   ├── Source Run Configuration
│   ├── Initiated By User
│   └── Created At
│
├── Run Snapshot
│   └── 创建后不可修改
│
└── Execution Information
    ├── Status
    ├── Scheduler Job Reference
    ├── Submitted At
    ├── Started At
    ├── Finished At
    └── Exit Information
```

平台先创建 Run 并固定 Run Snapshot，再向底层调度系统提交任务：

```text
创建 Run
→ 固定 Run Snapshot
→ 提交调度任务
→ 关联 Scheduler Job
→ 更新 Run 执行状态
```

Run 执行过程中可以关联或产生：

```text
Run
├── Scheduler Job
├── Log
├── Artifact
├── Resource Usage Record
└── Metric（可选）
```

其中，Artifact 和 Resource Usage Record 沿用前文定义。

Metric 可以表示单个结果值，也可以表示随执行过程变化的时间序列，主要用于：

```text
结果可视化
训练曲线展示
不同 Run 之间的结果比较
最佳 Run 筛选
```

Metric 与 Resource Usage Record 承担不同职责：

```text
Metric
→ 用户程序产生的业务或实验结果
→ 例如 accuracy、loss、score

Resource Usage Record
→ 平台采集的执行和资源使用信息
→ 例如运行时长、CPU、内存和 GPU 使用情况
```

核心关系可以概括为：

```text
Run Configuration
→ 可编辑、可复用的运行方案

Run Snapshot
→ 本次执行不可变的配置事实

Run
→ 一次独立执行及其完整生命周期记录
```

#### 3.1.7 Profile 与场景扩展

| 中文名称 | 英文名称 | 定义 |
| :------ | :----- | :--- |
| Profile | Profile | 由 User 或 User Group 拥有，将平台基础能力、默认配置和工作流组合为特定使用场景的扩展定义 |
| Profile 可见性 | Profile Visibility | 控制谁能找到并读取 Profile 及其不可变版本：OWNER_SCOPE 仅 Owner 范围内可见，PUBLIC 对所有已认证 User 可见 |
| Profile 版本 | Profile Version | 某个 Profile 已发布的不可变版本 |
| Profile 实例 | Profile Instance | 某个 User Group 启用确定 Profile Version 后形成的场景配置 |

Profile 是建立在平台基础领域模型之上的场景扩展机制：

```text
Profile
├── 组合平台基础能力
├── 提供场景工作流
├── 提供默认配置
├── 提供场景导航与界面
└── 可以引入场景专属对象
```

User Group 启用 Profile 时，应形成对应的 Profile Instance：

```text
User Group
└── Profile Instance
    └── Profile Version
```

Profile 与 User Group 是不同概念：

```text
User Group
→ 成员、权限、共享资产和组拥有对象的独立治理边界

Profile
→ User Group 中启用的场景能力和工作流
```

Profile 必须遵守以下规则：

```text
1. Profile Instance 必须且只能属于一个 User Group，不得属于 User。

2. Profile Instance 必须引用该 User Group 可读取的确定 Profile Version。

3. Profile Version 发布后不得原地修改；
   Profile 发生变化时应发布新版本。

4. Profile 的 Ownership 和可读性不改变 Profile Instance 的归属，也不授予目标 User Group 其他权限或资格。

5. Profile 可以组合基础能力并引入场景专属对象，但不能改变 User、User Group、Project、Run 等基础对象的归属关系。

6. Profile 不能绕过平台既有的权限、版本不可变性和执行隔离规则。

7. Profile Version 更新后，不应静默改变已有 Profile Instance；
   是否升级应由平台按照明确规则处理。
```

#### 3.1.8 Activity 与 Notification

| 名称 | 定义 |
| :--- | :--- |
| Activity | 对已经发生的重要操作形成的不可修改记录，说明谁在什么时候对哪个对象做了什么 |
| Notification | 发送给特定接收者的提醒，告知值得关注的变化或需要处理的事项 |

Activity 记录操作者（User，或适用时的平台系统）、动作、作用对象和发生时间。

以下活动归入对应对象视图，并按该对象当前 Owner 边界校验：

```text
Project、其从属对象或 Run ─────────────▶ Project
Environment 或其 Version ──────────────▶ Environment
Shared Resource 或其 Version ──────────▶ Shared Resource
User Group 或 Membership ──────────────▶ User Group
```

Notification 可以关联 Activity，也可以独立存在。

---

### 3.2 核心对象关系

平台中的对象关系主要分为两类：

```text
领域对象之间主要存在：

归属关系
→ 表示对象位于哪个管理和生命周期边界内。

引用关系
→ 表示对象使用或指向另一个对象，
  不改变被引用对象的归属。

关系对象
→ 用于记录两个或多个对象之间具有独立业务语义的关系，
  如 Membership、Grant 和 Fork Relation。
```

#### 3.2.1 对象归属关系

主要对象归属如下：

```text
Platform
└── Compute Plan

User
├── Project *
├── Template *
│   └── Template Revision
├── Profile *
│   └── Profile Version
├── Environment *
│   └── Environment Version
├── Shared Resource *
│   └── Shared Resource Version
├── Variable
├── Secret
├── Resource Entitlement
└── Entitlement Request

User Group
├── Project *
├── Template *
│   └── Template Revision
├── Profile *
│   └── Profile Version
├── Profile Instance
├── Variable
├── Secret
├── Environment *
│   └── Environment Version
└── Shared Resource *
    └── Shared Resource Version

Project
├── Variable
├── Secret
├── Project Working State
├── Project Version
├── Project Branch
├── Run Configuration
└── Run
    ├── Run Snapshot
    ├── Log
    ├── Artifact
    ├── Metric
    └── Resource Usage Record
```

其中：

```text
* Project、Template、Profile、Environment 和 Shared Resource 分别由一个 User 或一个 User Group 拥有。

Profile Instance
→ 必须且只能属于一个 User Group。

Variable、Secret
→ 分别属于一个 User、一个 User Group 或一个 Project。

Resource Entitlement、Entitlement Request
→ 属于一个 User。

Project Working State、Project Version、Project Branch、Run Configuration
→ 属于对应 Project。

Run
→ 属于对应 Project。

Run Snapshot、Log、Artifact、Metric、Resource Usage Record
→ 属于对应 Run。

Template Revision
→ 属于上级 Template，并固有不可变文件清单。

Profile Version、Environment Version、Shared Resource Version
→ 属于各自的上级对象。

Compute Plan
→ 由 Platform 管理。
```

本图仅展示主要领域对象的归属关系，配置项、值对象和对象间引用关系不在本图中展开。

---

#### 3.2.2 对象引用关系

主要引用关系如下：

```text
Project Branch
└── Project Version

Run Configuration
├── Environment Version
├── Compute Plan
├── Input Binding
│   ├── Shared Resource Version
│   └── Artifact
└── Environment Variable
    ├── Literal Value
    ├── Standard Variable / Secret ──▶ Project / Project Owner
    └── Explicit User Variable / Secret ──▶ Initiated By User

Run
├── Initiated By User
└── Source Run Configuration（可选）

Run Snapshot
├── Project Version
├── Environment Version
├── Compute Plan
├── Input Binding
│   ├── Shared Resource Version
│   └── Artifact
└── Environment Variable
    ├── Fixed Literal / Variable Value
    └── Exact Secret Reference

Resource Entitlement
└── Compute Plan

Template Revision
├── 不可变文件清单（固有内容）
├── 来源记录（Source Project 与 Source Project Version 的持久标识）
└··▶ Source Project Version（可选实时导航）

Profile Instance
└── Profile Version（来源引用）
```

其中：

```text
Project Branch
→ 指向 Project Version，Branch 可变化，Version 不变。

Run Configuration
→ 保存可编辑、可复用的运行配置与资源引用。

Run Snapshot
→ 固定本次执行使用的确定版本、输入和配置；
  Run 执行以 Run Snapshot 为准。

Project Version
→ 提供 Run 自身的项目内容。

Input Binding
→ 提供额外输入内容，可引用 Shared Resource Version 或 Artifact。

Resource Entitlement
→ 表示 User 获得某个 Compute Plan 的使用资格。

Template Revision
→ 包含确定的文件清单和来源记录；
  Source Project Version 仅作为可选导航。

Profile Instance
→ 引用当前 User Group 可读取的确定 Profile Version，引用不改变 Profile 的 Ownership。
```

---

#### 3.2.3 关系总览

图例：

```text
├──   归属关系
──▶   引用关系
··▶   可选引用关系
*     表示存在两种合法 Owner 类型
```

```text
User
├── Variable
├── Secret
├── Resource Entitlement ─────────▶ Compute Plan
├── Entitlement Request
├── Project *
├── Template *
│   └── Template Revision
├── Profile *
│   └── Profile Version
├── Environment *
│   └── Environment Version
└── Shared Resource *
    └── Shared Resource Version

User ── Membership(Role, Status) ── User Group

User Group
├── Project *
├── Template *
│   └── Template Revision
├── Profile *
│   └── Profile Version
├── Profile Instance ──────────────▶ Profile Version
├── Variable
├── Secret
├── Environment *
│   └── Environment Version
└── Shared Resource *
    └── Shared Resource Version

Project
├── Variable
├── Secret
├── Project Working State
├── Project Version ◀──── Project Branch
├── Run Configuration
│   ├──▶ Environment Version
│   ├──▶ Compute Plan
│   ├── Input Binding ──▶ Shared Resource Version / Artifact
│   └── Environment Variable ──▶ Project / Project Owner Variable / Secret
│                                or Initiated By User Variable / Secret
└── Run ──▶ Initiated By User
    ├··▶ Source Run Configuration
    ├── Run Snapshot
    │   ├──▶ Project Version
    │   ├──▶ Environment Version
    │   ├──▶ Compute Plan
    │   └── Input Binding ──▶ Shared Resource Version / Artifact
    ├── Log
    ├── Artifact
    ├── Metric
    └── Resource Usage Record

Platform
└── Compute Plan

Source Project Version
        ╲
     Fork Relation
        ╱
Derived Project

Template Revision（不可变文件清单、持久来源记录）··▶ Source Project Version（可选实时导航）

Activity ──▶ 操作者（User / Platform System）、作用对象
Notification ──▶ User
Notification ··▶ Activity / 来源对象

Grantor(User / User Group) ── Grant(USE, ALL / Environment / Shared Resource) ──▶ Grantee(User / User Group)
```

这里有几个关键语义：

```text
Membership
→ 连接 User 与一个确定 User Group，并记录 Role 和 Status。

Project
→ 由一个 User 或一个 User Group 拥有，并包含 Run Configuration、Run 及其从属对象；Visibility 控制其元数据和不可变 Project Version 的发现与读取。

Project Version
→ 提供 Run 自身的项目内容。

Input Binding
→ 提供额外输入内容，来源为 Shared Resource Version 或 Artifact。

Run Configuration
→ 保存可编辑、可复用的引用和配置；标准 Variable / Secret 引用按 Project > Project Owner 解析，
  显式 `user` 引用只使用 Initiated By User 的个人上下文。

Run Snapshot
→ 固定本次执行实际使用的确定版本、输入、普通值和 Variable 值；Secret 只固定 exact 引用。

Template
→ 由一个 User 或一个 User Group 拥有的发布与目录对象。

Template Revision
→ 固有不可变文件清单和来源记录；实时来源导航可选，
  从中创建的 Project 独立选择目标 Owner。

Profile
→ 由一个 User 或一个 User Group 拥有；Ownership 与 Profile Instance 的启用边界分离。

Profile Instance
→ 必须且只能属于启用它的 User Group，并引用该组可读取的确定 Profile Version。

Resource Entitlement
→ 使 User 获得 Compute Plan 的使用资格；Run 使用发起 User 的资格。

Grant
→ 由 Grantor 向 Grantee 授予 `USE`；可覆盖 Grantor 当前拥有的全部 Environment / Shared Resource，或某个具体顶层资产。

Environment、Shared Resource
→ 分别由一个 User 或一个 User Group 拥有；平台提供或运营的资产由平台运营的 User Group 持有。

Fork Relation
→ 记录新 Project 从哪个 Project Version 派生。

Activity
→ 记录对象上已完成的操作，可在相关对象、User Group 和 User 视图中查看。

Notification
→ 向确定 User 发送需要关注或处理的信息，可关联 Activity 或相关对象。
```

本图用于概括核心领域对象的主要归属和引用关系，不表示数据库表结构、外键关系或具体实现依赖。

---

### 3.3 核心产品规则

#### 3.3.0 规则标识与演进规范

核心产品规则使用 `GR-xxx` 作为稳定标识，其中 `GR` 表示 Global Rule。

规则编号按类别划分：

```text
GR-1xx  User Group、Ownership 与权限边界
GR-2xx  版本、快照与历史一致性
GR-3xx  Run 与执行
GR-4xx  资源使用与跨 Owner
GR-5xx  派生、复用与扩展
GR-6xx  Activity 与 Notification
GR-7xx ~ GR-9xx  保留给未来新增规则类别
```

同一区间内按顺序分配编号。规则编号用于标识规则本身，不表示其在文档中的排列顺序。

每条规则应具有唯一编号、简短名称和一个可判定的核心约束，并在必要时明确适用对象、条件和结果。

规则具有以下生命周期状态：

```text
Draft
→ 尚未形成正式基线，可以修改、删除、合并、拆分或重新编号。

Active
→ 已纳入正式规范基线，作为当前产品设计、实现和测试的有效约束。

Superseded
→ 已被其他规则替代，不再作为当前有效规则。

Retired
→ 对应约束已退出产品模型，不再适用。
```

规则完成必要评审并随正式规范版本形成基线后，由 `Draft` 转为 `Active`。

规则进入 `Active` 后，其编号不得复用，也不得因文档结构调整而重新编号。规则演进遵循以下原则：

1. 措辞修正、补充说明或消除歧义，且不改变核心业务约束时，保留原编号。
2. 同一业务约束随产品演进发生调整时，可以保留原编号，并通过规范版本、变更记录和 Git 历史保存其演进过程。
3. 规则被拆分、合并、职责发生根本变化或被新的规则体系取代时，应创建新的规则编号，并将原规则标记为 `Superseded`。
4. 对应约束不再适用时，将规则标记为 `Retired`；`Superseded` 和 `Retired` 的编号均不得复用。

是否仍属于同一条规则，以其约束的核心业务问题是否保持一致为判断依据。

引用当前规则时使用规则编号，如 `GR-303`；引用某一历史版本的规则时，应同时注明对应的规范版本。

#### 3.3.1 User Group、Ownership 与权限边界

##### **GR-101 — 对象归属**

Project、Template、Profile、Environment 和 Shared Resource 必须且只能由一个 User 或一个 User Group 拥有；平台提供或运营的 Environment 与 Shared Resource 由平台运营的 User Group 持有，不形成新的 Owner 或资产类型。Profile Instance 必须且只能属于一个 User Group；Variable 和 Secret 必须且只能属于一个 User、一个 User Group 或一个 Project；Resource Entitlement 和 Entitlement Request 必须属于 User。

##### **GR-102 — Membership 操作边界**

User 必须通过对应 User Group 的有效 Membership，才能以该组成员身份操作该组拥有的对象。每个 Membership 只作用于其连接的确定 User Group，Grant 不创建 Membership。

##### **GR-103 — Membership Role 权限**

User 在一个 User Group 中可执行的操作必须受该 Membership 的 Role 和 Status 约束；同一 User 在其他 User Group 中的 Membership、Role 或 Status 不参与判断。所有有效角色均可查看成员；Owner 可以邀请普通 Member、移除 Member 或 Admin、在 Member 与 Admin 之间变更角色并转移所有权；Admin 只能邀请和移除普通 Member；Member 不具有成员治理权限。普通邀请只产生 Member，Owner 身份只能通过所有权转移改变。

##### **GR-104 — User Group 所有权**

User Group 必须始终具有唯一的有效 Owner；Owner 转移完成前不得移除或退出原 Owner。

##### **GR-105 — 权限与资源资格分离**

User 创建 Run 时，平台必须分别校验其 Project 操作权限、对所引用资产的访问权、Variable 与 Secret 引用的可用性和授权，以及其 Resource Entitlement；User Group Ownership 或 Membership 不转移 Resource Entitlement。

##### **GR-106 — 平台管理权限与业务数据权限分离**

Platform 管理权限不授予以下业务数据的访问权：OWNER_SCOPE Project、Environment、Shared Resource，以及任何 User、User Group 或 Project scoped Variable / Secret。

全局 Run 运维只能使用独立的管理投影，返回身份引用与 Owner 边界、状态与时间、Scheduler Job Reference、资源请求与实际分配、排队原因代码和结构化异常分类。该投影不得复用普通 Run 详情，也不得返回 Run 名称、命令、工作目录、环境变量、其他 Run Snapshot 配置、Log、Artifact 内容，以及 Project、Project Version、Environment 或 Shared Resource 内容。

##### **GR-107 — Project Visibility 与操作边界**

Project Visibility 只能是 OWNER_SCOPE 或 PUBLIC。
OWNER_SCOPE Project 仅允许 Owner User，或在 exact owning User Group 中具有有效 Membership 的 User 发现和读取。
PUBLIC 允许所有已认证 User 发现和读取 Project 元数据及不可变 Project Version 内容，并从确定的 Project Version 创建独立 Project。
PUBLIC 不授予源 Project 的编辑、管理、Run 创建等。
PUBLIC 也不暴露 Run Configuration、任何 scoped Variable / Secret、Run、Log、Artifact 或 Project 内部 Activity。

---

#### 3.3.2 版本、快照与历史一致性

##### **GR-201 — 版本内容不可变**

Project Version、Template Revision、Profile Version、Environment Version 和 Shared Resource Version 创建后均不得原地修改，内容变化必须形成新版本。

##### **GR-202 — Run Snapshot 不可变**

Run Snapshot 创建后不得修改；Run 创建之后发生的配置变化不得回写已有 Run Snapshot。

##### **GR-203 — Artifact 内容不可变**

Artifact 创建后，其内容不得原地修改；需要保存不同内容时必须形成新的 Artifact。

##### **GR-204 — 历史对象不受后续修改影响**

可编辑对象及其配置的后续变化，不得回写已经生成的 Version、Revision 或 Run Snapshot。

##### **GR-205 — 确定引用不得漂移**

Run Configuration 和 Run Snapshot 必须引用确定的 Environment Version；其中的 Input Binding 必须引用确定的 Shared Resource Version 或 Artifact。默认值或可变别名不得改变已经确定的引用。精确引用只保证内容身份不漂移，不保证内容永久可用。

##### **GR-206 — 不可变性与生命周期独立**

不可变只表示对象在存续期间不得原地修改，不表示永久保留。Version、Artifact 内容、Log 和 Run 工作目录可以按照各自的保留策略到期或删除；精确引用的内容不可用时，不得自动改用其他内容。

Run Snapshot 只保存创建时确定的身份和配置，不延长其引用 Version、Artifact 或内容的保留期限。Run 与其 Run Snapshot 只能通过明确的生命周期操作或保留策略一并删除。

Template Revision 适用更强的内容保留约束。Revision 存续期间，其文件清单和对应内容必须保持可读取，并可用于创建 Project。Source Project 或 Source Project Version 到期或删除不得使 Revision 失效；来源记录继续保留，但实时导航可以不可用。

有权管理 Template 的 User 可以直接删除 Template。删除立即停止 Template 的发现、读取和新 Project 创建，并结束 Template 及其所属 Revision 的生命周期；已经创建的 Project 不受影响。

---

#### 3.3.3 Run 与执行规则

##### **GR-301 — Run 归属**

每个 Run 必须且只能属于一个 Project；Run Snapshot、Log、Artifact、Metric 和 Resource Usage Record 必须且只能属于对应 Run，并遵循所属 Project 的 Ownership 与生命周期边界。

##### **GR-302 — Run Snapshot 生成**

创建 Run 时，平台必须生成独立的 Run Snapshot，并在其中固定本次执行使用的 Project Version、执行配置及相关资源版本。

若 Run 基于 Run Configuration 创建，其内容必须在创建 Run 时解析并固化到 Run Snapshot。

##### **GR-303 — Run 执行配置依据**

Run 的执行必须以其 Run Snapshot 为唯一配置依据；创建 Run 后发生的 Project、Run Configuration 或相关资源变化不得改变本次执行配置。Snapshot 引用的精确内容不可用时，本次提交或执行必须失败并记录原因，不得解析替代版本。

##### **GR-304 — Secret 执行规则**

Run Snapshot 不得保存 Secret 明文；创建 Run 时必须确定并保存 exact Secret 引用，执行时由平台按该引用的当前有效授权安全取得当前值。

##### **GR-305 — 执行结果与执行快照分离**

Run Snapshot 只能记录执行开始前已确定的输入和配置；Log、Artifact、Metric 和 Resource Usage Record 等执行过程中或执行完成后产生的信息不得作为 Run Snapshot 的组成部分。

##### **GR-306 — Run 执行唯一性**

每个 Run 只能表示一次逻辑执行。用户对已有 Run 发起重新执行时，平台必须创建新的 Run 和新的 Run Snapshot，不得复用原 Run 表示新的执行。

##### **GR-307 — Run 发起 User**

每个 Run 必须记录唯一的 Initiated By User。平台以该 User 确定执行身份和显式 user Variable / Secret 引用的个人上下文，校验 Resource Entitlement，并归属资源使用记账与审计责任。标准 Variable / Secret 引用仍按 Project > Project Owner 解析。发起 Run 不使该 User 获得 Run 或其从属对象的 Ownership。

---

#### 3.3.4 资源使用与跨 Owner 规则

##### **GR-401 — Environment 与 Shared Resource 使用资格**

Owner User 可以管理、发布和使用自己的 Environment 或 Shared Resource；User Group-owned 资产由具体 User 按该组有效 Membership 的 Role / Status 操作；跨 Owner 使用必须命中资产当前 Owner 作为 Grantor 发出的有效 USE Grant。

##### **GR-402 — Grant 主体、范围与版本分离**

Grantor 和 Grantee 只能是 User 或 User Group，Action 只能是 `USE`。Target 只能是 `ALL` 或顶层 Environment / Shared Resource；`ALL` 只覆盖当前 Owner 为 Grantor 的资产，包括其后续新建或取得的资产。Grant 不直接授予 Version，不以 Project 为 Grantor、Grantee 或 Target，也不授予管理、发布、归档、转移等生命周期权限。

##### **GR-403 — Input Binding 内容确定性**

Run Configuration 中的 Input Binding 必须引用确定的 Shared Resource Version 或 Artifact；创建 Run 时，该引用必须固定到 Run Snapshot。

##### **GR-404 — 输入源只读**

通过 Input Binding 提供的输入不得被 Run 原地修改；运行过程中需要产生或修改的内容必须写入本次 Run 的可写空间，并按需要形成 Artifact。

##### **GR-405 — Artifact 所有权边界**

Artifact 可以直接作为同一 Project Owner 边界中后续 Run 的 Input Binding 来源；跨 Owner 使用 Artifact 内容时，必须先将其发布为 Shared Resource，并按照 Shared Resource 的授权规则使用。

##### **GR-406 — Compute Plan 使用资格**

发起 User 只能使用其有效 Resource Entitlement 所允许的 Compute Plan。

##### **GR-407 — Secret 派生隔离**

Variable、Secret 的值和访问权限不得因 Fork、Template 或其他跨 Owner 的派生、复用行为而复制或继承。配置中的引用表达式可以复制，但只能在目标 Project、其 exact Owner User 或 exact owning User Group，以及目标 Run 的 Initiated By User 上下文中重新解析并满足权限条件。

##### **GR-408 — Ownership 变更后的授权失效**

Ownership 转移不得改写已有 Version，也不得改变既有 Run Snapshot 中记录的身份和配置。Grant 仅在 Grantor 仍是目标资产当前 Owner 时作用于该资产；资产转移后，原 Grantor 的 `ALL` 或单资产 Grant 自然不再适用，新 Owner 可以重新授权。User Group 内部 `MembershipRole.OWNER` 变更不属于资产 Ownership 转移，不影响以该 User Group 为 Grantor 的 Grant。转移不延长所引用内容的保留期限；重新执行时，仍须校验当时有效的授权和内容可用性。

---

#### 3.3.5 派生、复用与扩展规则

##### **GR-501 — Fork 来源与追踪**

Fork 必须从确定的 Project Version 创建新的 Project，并记录 Source Project Version 与目标 Project 之间的 Fork Relation。

##### **GR-502 — Fork 后独立**

Fork 完成后，目标 Project 具有独立生命周期；源 Project 与目标 Project 的后续修改或删除不得相互影响。

##### **GR-503 — Fork 权限与历史隔离**

User 只有按 Project Visibility 可读取源 Project，才能从确定的 Project Version 创建派生 Project。PUBLIC 允许所有已认证 User 发起 Fork，但仍须单独校验目标 Owner 下的 Project 创建权限。

Fork 可以复制确定 Project Version 的内容和可复用资源引用。Run Configuration 只有在发起 User 是 Owner User，或其在 exact owning User Group 中的有效 Membership Role / Status 允许该操作时，才能复制。PUBLIC 本身不暴露或复制 Project Working State、Project Branch 或 Run Configuration。

目标 Owner 必须显式选择 User 或 User Group。Fork 不得复制或继承 Membership、Role、Variable / Secret 值或访问权、Resource Entitlement、Run 历史或执行结果。复制资源引用也不转移使用资格；实际使用时，仍须校验目标 Project 的操作权限、资产授权和发起 User 的执行资格。

Run Configuration 复制仅适用于 From Project Version。From Template Revision 只按其不可变文件清单创建 Project，不复制 Run Configuration。

##### **GR-504 — Template 创建独立性**

从 Template Revision 创建 Project 时，必须以该 Revision 的不可变文件清单作为唯一内容来源，并创建独立 Project 及其初始 Project Version；不得再从 Source Project 或 Source Project Version 读取内容。目标 Owner 必须显式选择 User 或 User Group。新 Project 不与 Template 或源 Project 建立自动更新或权限继承关系。

创建过程只复制 Revision 固定的文件，不复制源 Project 的其他状态，也不继承其权限或资格。Template 或 Template Revision 的后续状态变化，以及 Template 发布的新 Revision，均不得改变已经创建的 Project。

##### **GR-505 — Profile Instance 版本固定**

Profile Instance 必须且只能属于启用它的 User Group，并基于该组可读取的确定 Profile Version 创建。创建后，源 Profile 或 Profile Version 的变化和删除不得改变该 Instance 已采用的场景定义。

##### **GR-506 — Profile 显式升级**

已有 Profile Instance 切换到其他 Profile Version 时，必须通过明确的升级操作完成，不得因 Profile 默认版本或最新版本变化而静默升级。

##### **GR-507 — Profile 扩展边界**

创建、读取或启用 Profile 不改变 Membership，也不授予 Environment 或 Shared Resource 使用资格、Variable 或 Secret 访问权、Resource Entitlement，以及 Run 或 Scheduler 权限。Profile 中的引用在启用或使用时，必须在目标 User Group 和 Initiated By User 的上下文中按既有规则重新校验，不得绕过版本不可变性或 Run Snapshot 规则。

##### **GR-508 — Template 发布与读取边界**

Template Visibility 只能是 OWNER_SCOPE 或 PUBLIC。OWNER_SCOPE 仅允许 Owner User，或在 exact owning User Group 中具有有效 Membership 的 User 发现和读取；PUBLIC 允许所有已认证 User 发现和读取。具有 Template Revision 读取权限的 User 可以按 GR-504 创建独立 Project。

弃用的 Template 仍可读取和使用，但必须显著标记，且不得设为推荐或精选。取消发布是可逆操作；取消后，普通用户不能再发现、读取或使用 Template，Owner 边界内有管理权限的 User 仍可管理它及其 Revision。

Template Revision 只能由具有相应权限的 User，从同一 Owner 的确定 Project Version 发布。Revision 只包含不可变文件清单和来源记录，不包含源 Project 的其他状态、配置、权限、资格或运行数据。仅凭 Project Visibility 获得读取权限，不足以跨 Owner 发布 Template。

读取 Template Revision 只提供来源记录，不授予源 Project 访问权。进入 Source Project Version 仍须满足 GR-107，且来源删除后可以不可用；来源删除与内容保留遵循 GR-206。

##### **GR-509 — Profile 读取与启用边界**

Profile Visibility 必须且只能是 OWNER_SCOPE 或 PUBLIC。OWNER_SCOPE Profile 仅允许 Owner User，或 exact owning User Group 中具有有效 Membership 的 User 发现和读取；PUBLIC 允许已认证的平台 User 发现和读取 Profile 元数据及不可变 Profile Version。

User Group 仅可基于该组拥有的 Profile，或 PUBLIC Profile 中的确定 Profile Version 创建或升级 Profile Instance；执行操作的 User 还必须在目标 User Group 中具有管理 Profile Instance 的有效 Membership、Role 和 Status。跨 Owner 启用只允许 PUBLIC Profile，Profile 可读性不扩大 GR-507 规定的权限和资格边界。

---

#### 3.3.6 Activity 与 Notification 规则

##### **GR-601 — Activity 完成性与唯一性**

一个有意义且已经完成生效的领域动作至多形成一条不可变 Activity；未成功生效的操作不形成 Activity，Run 进入 `FAILED` 等已经生效的状态变化可以形成 Activity。

##### **GR-602 — Activity 视图不复制记录**

同一条 Activity 可以显示在多个相关视图中，无需重复记录。对象视图显示该对象的 Activity；User Group 活动汇总显示该组、其 Membership，以及该组拥有对象中需要汇总的 Activity；个人相关视图只显示与 User 存在明确操作者、发起者、受影响者或参与者关系的 Activity。

User 拥有的资产不会仅因该 User 是某个 User Group 的成员而进入组活动汇总。被多个 Project 引用的资产发生变化时，Activity 只记录在该资产上；需要提醒时，向相关 User 发送 Notification。

##### **GR-603 — Activity 查看权限**

Activity 必须按作用对象归入对象的当前 Owner 边界授权。Project、Environment 或 Shared Resource 的 Activity 仅允许 Owner User，或 exact owning User Group 中具有有效 Membership 且 Role / Status 允许的 User 查看；User Group 直接 Activity 仅允许该组中具有相应权限的有效成员查看。User Group 或个人视图不得绕过这些边界，PUBLIC Project 与 USE Grant 均不公开 Activity。

##### **GR-604 — Activity 与 Notification 分离**

Activity 没有未读、完成或送达状态，也不替代 Notification、Audit Log、Run Log 或调度遥测。Notification 可以选择关联 Activity；维护、配额、提醒或邀请等 Notification 可以不关联 Activity。

---

### 3.4 核心领域操作

#### 3.4.1 User Group 生命周期与治理操作

##### 创建 User Group

具有创建权限的 User 可以创建 User Group。创建时必须建立创建者的 Membership，并确定唯一 Owner。

##### 删除 User Group

删除 User Group 前必须先处理其拥有的资产、Variable 和 Secret；删除不得移除 User 身份，也不得影响 User 在其他 User Group 中的 Membership。

##### 管理 Membership

User Group 可以建立 Membership、变更 Role 和 Status、退出或移除成员；变更仅影响对应 User 在该组中的成员身份和操作权限，不改变组拥有的对象，并须保持唯一有效 Owner。普通邀请只建立 Member；只有 Owner 可以在 Member 与 Admin 之间变更 Role，Admin 只能邀请和移除普通 Member；Owner 不得通过普通 Role 变更产生或取消。

##### 转移 User Group Owner

User Group 可以将 Owner 转移给另一有效成员，并始终保持唯一有效 Owner。

##### 管理 User 与 User Group Variable / Secret

User 可以创建、修改和删除自己的 Variable，以及创建、替换、轮换和删除自己的 Secret。Secret 值设置后不可读取，有权管理的 User 只能查看其元数据。

User Group 中具有相应权限的 User 可以管理该组的 Variable 和 Secret；Secret 值同样不可读取，只能查看元数据以及创建、替换、轮换或删除。

#### 3.4.2 Project 生命周期、版本与运行配置操作

##### 创建 Project

User 或 User Group 可以拥有新的 Project，并产生其初始 Project Working State。

Project 支持以下初始化来源：

- Blank：创建空白 Project；
- From Project Version：基于确定的 Project Version 创建独立 Project，并建立 Fork Relation；
- From Template Revision：按 GR-504 创建独立 Project 及其初始 Project Version。

From Project Version 按 GR-107 与 GR-503 校验；From Template Revision 按 GR-504 与 GR-508 校验。两种来源都必须显式选择 User 或 User Group 作为目标 Owner。

##### 管理 Project Visibility

有权管理 Project 的 User 可以在 OWNER_SCOPE 与 PUBLIC 之间设置 Project Visibility；其读取、Fork 与操作边界遵循 GR-107。

##### 编辑 Project Working State

Project Working State 表示 Project 当前可编辑的工作内容。

只有 Owner User，或 exact owning User Group 中具有有效 Membership 且 Role / Status 允许编辑的具体 User，才能修改 Project Working State；PUBLIC 不授予编辑权限。对 Working State 的修改不得改变已经创建的 Project Version，也不得影响已有 Run Snapshot。

##### 创建 Project Version

可以基于 Project 当前 Working State 创建新的 Project Version。

Project Version 创建后内容不可变，用于固定某一确定的 Project 状态，并可以作为创建 Run 或新 Project 的确定来源。

后续对 Working State 的修改不得改变已有 Project Version。

##### 管理 Project Branch

Project 可以创建、移动和删除 Project Branch。

Project Branch 是指向本 Project 某一确定 Project Version 的可变引用；移动 Branch 只改变其指向，不修改任何 Project Version。

##### 管理 Project Variable 与 Secret

有权管理 Project 配置的 User 可以创建、修改和删除 Project Variable，以及创建、替换、轮换和删除 Project Secret。Project Secret 值设置后不可读取，只能查看其元数据。

##### 管理 Run Configuration

有权操作 Project 的 User 可以创建、修改和删除 Run Configuration。Run Configuration 必须引用确定的 Environment Version；Input Binding 必须引用确定的 Shared Resource Version 或 Artifact；环境变量可以使用标准 Project > Project Owner 引用或显式 Initiated By User 引用。

创建 Run 时，平台重新校验这些引用。所有 Variable 和 Secret 引用必须解析成功并满足授权，Variable 值和 exact Secret 引用随其他配置固定到 Run Snapshot；后续修改 Run Configuration 不得改变已有 Snapshot。

##### 删除 Project

具有相应权限的主体可以删除 Project。

Project 删除时，其 Working State、Project Version、Project Branch、Run Configuration、Project scoped Variable 与 Secret，以及归属于该 Project 的 Run 和 Run 从属对象随其生命周期结束。

源 Project 删除不影响已经形成独立生命周期的对象。Template Revision 的保留按 GR-206 处理，实时来源导航与读取按 GR-508 处理。

#### 3.4.3 Run 生命周期与执行操作

##### 创建 Run

具体 User 可以在有权创建 Run 的 Project 下发起创建。平台按 GR-105 完成独立校验，记录 Run 的 Initiated By User，把确定的 Project Version、解析后的普通值与 Variable 值及 exact Secret 引用随 Run Configuration 固定到新的 Run Snapshot；任何未解析、未授权或内容不可用的引用都必须使创建失败。

##### 提交与执行 Run

Run 按照其 Run Snapshot 提交并执行；执行时只读取 Snapshot 中已经固定的版本、输入、普通值、Variable 值和 exact Secret 引用。

执行过程中，平台按照 Snapshot 中的 exact Secret 引用重新校验当前有效授权并安全取得当前值；无法取得时不得执行用户程序。一个 Run 表示一次逻辑执行。

##### 更新 Run 执行状态与执行信息

Run 在执行过程中可以更新 Status、Submitted At、Started At、Finished At、Exit 信息和 Scheduler Job Reference 等执行信息。

这些信息描述 Run 的实际执行过程，不属于 Run Snapshot，也不得改变 Snapshot 中已经固定的执行配置。

##### 记录执行输出与结果

Run 执行过程中及执行结束后，可以产生 Log、Metric 和 Resource Usage Record，并按照 Artifact Collection Rules 收集 Artifact。

Artifact 内容形成后不可变，并可以按照相应资源规则作为后续 Run 的输入或发布为 Shared Resource。

##### 取消 Run

具有相应权限的主体可以取消尚未结束且允许取消的 Run。

取消结束本次逻辑执行，但不删除 Run、Run Snapshot 以及此前已经产生的执行记录和结果。

##### 重新执行 Run

重新执行可以尝试复用原 Run Snapshot 记录的精确身份与配置，但必须创建新的 Run 和 Run Snapshot，并重新校验当前权限、资源资格及引用内容可用性；任一依赖不可用时不得漂移到其他版本。

#### 3.4.4 资源、授权与算力资格操作

##### 管理 Environment 与 Environment Version

有权管理 Environment 的 User 可以构建和校验环境定义，并在校验成功后发布不可变 Environment Version。

##### 管理 Shared Resource 与 Shared Resource Version

有权管理 Shared Resource 的 User 可以上传或导入资源内容，并在校验通过后发布不可变 Shared Resource Version。

##### 转移 Environment 或 Shared Resource

Environment 或 Shared Resource 的 Ownership 转移遵循 GR-408。

##### 管理跨 Owner 资产 Grant

Asset Owner 可以向 User 或 User Group 建立、调整或撤销 USE Grant；授权范围可以是该 Owner 当前及以后拥有的全部 Environment / Shared Resource，或某个具体顶层资产。

User-owned 资产由该 User 管理 Grant；User Group-owned 资产由有效成员按该组 Membership 的 Role / Status 对应权限管理，不把 `MembershipRole.OWNER` 等同于资产 Owner。实际执行操作的 User 只作为操作者记录。

##### 管理 Compute Plan

Platform 可以创建、调整和停用 Compute Plan。

Compute Plan 表示面向用户的算力资源与限制组合，不直接等同于底层调度系统对象。其后续变化不得改变已有 Run Snapshot 中已经固定的执行配置。

##### 管理 Entitlement Request 与 Resource Entitlement

User 可以针对 Compute Plan 提交 Entitlement Request。

请求经处理后可以创建、调整或延续该 User 的 Resource Entitlement。创建 Run 时，创建的 User 必须具有所选 Compute Plan 的有效 Resource Entitlement。

#### 3.4.5 Template 与 Profile 复用扩展操作

##### 管理 Template 与 Template Revision

User 或 User Group 可以作为唯一 Owner 创建和维护 Template；发布、读取与来源记录遵循 GR-508。

Template 的弃用、取消发布和删除，以及 Template Revision 的保留与清理，遵循 GR-206 与 GR-508。

从 Template Revision 创建 Project 遵循 GR-504。

##### 管理 Profile 与 Profile Version

User 或 User Group 可以作为唯一 Owner 创建、维护和删除 Profile，设置 GR-509 定义的 Profile Visibility，并创建不可变 Profile Version。

Profile Version 表示某一确定的扩展定义。Profile 后续发布的新 Version 不得自动改变已有 Profile Instance。

##### 管理 Profile Instance

User Group 可以按 GR-505 与 GR-509，基于可读取的确定 Profile Version 创建只属于该组的 Profile Instance，并将该版本的扩展定义固化为 Effective Definition；不得创建 User-scoped Profile Instance。

Profile Instance 可以维护 User Group-specific Configuration，并保留 Source Profile Version 作为来源引用；其生命周期不依赖源 Profile 或 Profile Version 持续存在。

Profile Instance 可以按 GR-506 与 GR-509 显式升级至另一可读取的确定 Profile Version，并重新固化 Effective Definition。User Group 可以删除不再需要的 Profile Instance。

## 四. 系统架构设计

### 4.0 速查表

```text
运行边界
→ API Backend / Background Worker

输入边界
→ HTTP API / Async Work / Scheduled Task

业务边界
→ Application / Domain

基础设施边界
→ Ports & Adapters

具体外部能力
→ Repository
→ Version Control
→ Scheduler
→ Storage
→ Secret Provider
→ Identity Provider

依赖规则
→ Dependency Inversion
→ Dependency Injection

具体基础设施
→ PostgreSQL
→ Git
→ slurmrestd / Slurm
→ Shared FS
→ USTC CAS
```

### 4.1 架构目标与总体形态

系统采用**模块化单体**作为主要应用架构，以第三章定义的领域模型和产品规则作为业务语义基础。

后端采用轻量领域驱动的分层设计：

```text
                    Inbound Adapters

        HTTP API       Async Work       Scheduled Task
            │              │                  │
            └──────────────┼──────────────────┘
                           ▼
                     Application
                    ↙           ↘
                Domain          Ports
                                  ▲
                                  │ implements
                          Infrastructure
```

> API 接请求，Application 办事情，Domain 定规则；Application 通过 Port 要求外部能力，Infrastructure 负责真正连接 PostgreSQL、Slurm 和文件系统。

Application 通过抽象 Port 使用持久化、调度、存储等外部能力，Infrastructure 提供具体实现，并通过依赖注入完成组合。

整体设计遵循以下原则：

```text
领域规则与基础设施实现分离

API 负责外部交互，不承载核心业务规则

Application 负责领域操作和用例编排

Domain 不依赖 FastAPI、PostgreSQL、Slurm 等具体技术

持久化、版本控制、调度、存储等外部能力通过 Port 隔离

系统初期保持模块化单体，不按领域模块提前拆分微服务

耗时和后台流程由 Background Worker 脱离 HTTP 请求生命周期处理
```

### 4.2 系统总体架构

目标系统采用模块化单体架构，主要由 API Backend 与 Background Worker 两类运行组件组成。
二者共享同一套 Application、Domain 和基础设施接口，但具有不同的运行入口和生命周期；
当前先有限实现模块化单体，等之后稳定了再拆分微服务。

API Backend 负责处理用户发起的 HTTP 请求；Background Worker 负责脱离 HTTP 请求生命周期的后台任务。系统任务还可以通过 Scheduled Task Adapter 定时触发。不同入口最终统一调用 Application，由 Application 编排领域操作，并通过 Port 使用数据库、版本控制、调度器、存储和 Secret 等外部能力。

```text
                                  User / Browser
                                        │
                                        │ HTTP / JSON
                                        ▼
                              ┌────────────────────┐
                              │    API Backend     │
                              │  HTTP API Adapter  │
                              └─────────┬──────────┘
                                        │
                                        │
                        ┌───────────────┴───────────────┐
                        │                               │
                        │                        Identity Provider
                        │                               │
                        │                               ▼
                        │                            USTC CAS
                        │
                        ▼
                  ┌─────────────┐
                  │ Application │
                  └──────┬──────┘
                         │
               ┌─────────┴─────────┐
               ▼                   ▼
            Domain          Outbound Ports
                                 │
      ┌──────────┬────────────┬──────────┬─────────┬─────────┬──────────┐
      ▼          ▼            ▼          ▼         ▼         ▼
   Repository  Version     Scheduler   Storage   Runtime    Secret
      Port     Control Port    Port       Port      Port     Provider
      │          │            │          │         │          │
      ▼          ▼            ▼          ▼         ▼          ▼
   PostgreSQL   Git       slurmrestd  Shared FS  Apptainer  Secret Store
                              │                  Conda
                              ▼                  Native
                           Slurm


                  Application
                       │
                       │ dispatch
                       ▼
              ┌─────────────────────┐
              │ Async Work Boundary │ ← Application 的 outbound 边界
              └──────────┬──────────┘
                         │
                         │ consume
                         ▼
              ┌─────────────────────┐
              │  Background Worker  │ ← Application 的 inbound adapter
              │    Worker Adapter   │
              └──────────┬──────────┘
                         │
                         ▼
                    Application

上图说的是前一个 Application Use Case 派发后台工作；后一个 Application Use Case 被 Worker 触发。


              Timer / Scheduling Mechanism
                         │
                         ▼
              ┌─────────────────────┐
              │ Scheduled Task      │
              │ Adapter             │
              └──────────┬──────────┘
                         │
                         ▼
                    Application
```

Application 负责用例编排并调用 Domain 执行业务规则，同时通过 Repository、Version Control、Scheduler、Storage、Secret Provider 等 Port 使用外部能力。具体基础设施由 PostgreSQL、Git、slurmrestd / Slurm、Shared FS 和 Secret Store 等提供。

Environment 与 Shared Resource 在 Domain 中保留独立模型和类型校验，Background Worker 完成 Environment 构建与校验或 Shared Resource 内容处理与校验，并在校验通过后发布不可变 Version。

身份认证通过外部 Identity Provider 接入 USTC CAS；认证后的身份由平台映射为 User，再按照 Membership、Role 和 Eligibility 等领域规则进行授权。

### 4.3 后端分层与依赖边界

后端采用分层设计：

```text
API Layer
    ↓
Application Layer
    ↓
Domain Layer

Application Layer
    ↓
Ports
    ↑
Infrastructure
```

API Layer 负责处理 HTTP 请求与响应；Application Layer 负责用例编排；Domain Layer 承载领域对象、规则与核心业务逻辑。

Application 通过 Repository、Scheduler、Storage、Version Control、Secret Provider 等 Port 使用外部能力，Infrastructure 提供这些 Port 的具体实现。

Application 和 Domain 不直接依赖 PostgreSQL、Slurm、Shared FS 等具体基础设施；具体实现通过依赖注入在系统组合入口中提供。

API Backend 与 Background Worker 共享同一套 Application、Domain 与 Port，仅具有不同的调用入口。

### 4.4 前端核心技术选型

| 类别 | 技术选型 | 主要职责 |
| ---- | ----- | --------- |
| JavaScript 运行时 | **Node.js 24 LTS** | 前端开发、构建、测试及代码生成 |
| 包管理器 | **pnpm 11** | 依赖安装、脚本执行及前端 Monorepo 管理 |
| 前端框架 | **React** | 构建组件化用户界面 |
| 开发语言 | **TypeScript** | 提供静态类型检查和前端模型约束 |
| 构建工具 | **Vite** | 开发服务器、热更新及生产构建 |
| 页面路由 | **React Router** | 路由匹配、嵌套路由、页面布局及路由参数管理 |
| 主组件库 | **Primer React** | 提供 GitHub 风格的基础组件、导航、表单和页面布局组件 |
| 设计变量 | **Primer Primitives** | 管理颜色、间距、圆角、字体及亮暗主题 |
| 图标库 | **Primer Octicons** | 提供与 Primer 视觉体系一致的图标 |
| 自定义样式 | **CSS Modules** | 实现 107 Workspace 专属布局和业务组件样式 |
| 服务端状态 | **TanStack Query** | API 数据查询、缓存、刷新、Mutation 和错误状态管理 |
| API 类型生成 | **openapi-typescript** | 根据 FastAPI OpenAPI 文档生成 TypeScript 接口类型 |
| HTTP 客户端 | **openapi-fetch** | 基于 OpenAPI 类型执行类型安全的 HTTP 请求 |
| Query API 集成 | **openapi-react-query** | 将类型安全 API 请求与 TanStack Query 集成 (可选) |
| 表单管理 | **React Hook Form** | 管理表单字段、提交状态和校验错误 |
| 输入校验 | **Zod** | 前端输入运行时校验及 TypeScript 类型推导 |
| 单元测试 | **Vitest** | 测试工具函数、模型转换和业务逻辑 |
| 组件测试 | **React Testing Library** | 从用户操作角度测试组件行为 |
| API Mock | **MSW** | 在测试和独立前端开发中模拟后端 API |
| 端到端测试 | **Playwright** | 测试登录、User Group 管理、Run 提交等完整业务流程 |

前端技术栈最终确定为：

```text
React + TypeScript + Vite
Primer React + Primer Primitives + Primer Octicons
CSS Modules
React Router
TanStack Query
OpenAPI 类型安全客户端
React Hook Form + Zod
Vitest + React Testing Library + MSW + Playwright
```

### 4.4 技术选型与运行形态

| 范围 | 选型 |
| --- | --- |
| 后端语言 | Python |
| Python 项目与依赖管理 | uv |
| Web Backend | FastAPI |
| 身份认证 | USTC CAS |
| 关系型数据库 | PostgreSQL |
| Project 内容与版本管理 | Git |
| 集群调度 | Slurm |
| Slurm 接入 | slurmrestd |
| 文件存储 | Shared File System |
| 计算运行环境 | Apptainer / Conda / Native |
| 应用架构 | Modular Monolith |
| 业务组织 | DDD-lite / Layered Architecture |
| 基础设施边界 | Ports & Adapters |
| 依赖管理 | Dependency Inversion + Dependency Injection |
| 后台任务 | Async Work Boundary + Background Worker |
| 部署形态 | Container-ready |

前端参考 GitHub / Primer 的布局模式与信息层级；
后端暂采用模块化单体架构。API Backend 与 Background Worker 共享 Application、Domain 与 Infrastructure 代码。

## 五. 工程实现规划

本章规定工程组织、实现方式和演进约束。具体 Schema、API、Port 和基础设施细节，在对应垂直切片进入开发前按需设计。

### 5.1 仓库与目录组织

项目采用 Monorepo：

```text
107-workspace/
├── frontend/ # 暂未形成稳定版本，fronted 需要重构，当前代码仅作为参考
│   ├── src/
│   │   ├── app/
│   │   ├── features/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── api/
│   │   └── lib/
│   └── tests/
│
├── backend/
│   ├── src/
│   │   └── workspace107/
│   │       ├── api/
│   │       ├── user_group/
│   │       ├── project/
│   │       ├── run/
│   │       ├── resource/
│   │       ├── template/
│   │       ├── profile/
│   │       ├── infrastructure/
│   │       ├── worker/
│   │       └── bootstrap/
│   ├── tests/
│   ├── migrations/
│   ├── pyproject.toml
│   └── uv.lock
│
├── contracts/
│   ├── README.md
│   └── openapi.json
│
├── deploy/
│   ├── README.md
│   └── compose.yaml
│
├── docs/
│   ├── product/
│   ├── contributing/
│   ├── operations/
│   ├── decisions/
│   ├── journal/
│   ├── references/
│   └── archive/
├── scripts/
│   ├── workspace.py
│   ├── tasks/
│   └── platform/
├── .github/
├── Makefile
└── README.md
```

后端优先按领域责任组织，各领域模块内部再按实际需要划分 Domain、Application 和 Port；Infrastructure 承载 PostgreSQL、Git、Slurm、Shared FS、Secret 等具体实现。

目录是当前工程基线，不是永久兼容契约；真实责任边界变化时允许调整。

### 5.2 垂直切片与持续设计

功能以垂直切片推进，每次尽量形成一条可验证的完整能力：

```text
用户操作
   ↓
Frontend / API
   ↓
Application
   ↓
Domain
   ↓
Port / Infrastructure
   ↓
可验证结果
```

首个切片不要求提前建立尚未被真实需求证明需要的抽象，但仍必须保持正确的责任归属和依赖方向。

当重复领域知识、新责任、新变化轴或明显耦合真实出现时，应及时重构，而不是持续在旧结构上增量堆叠。

整体采用 Continuous Design：

```text
实现
→ 验证
→ 发现结构问题
→ 重构 / 抽象
→ 继续实现
```

### 5.3 重构与兼容性边界

正式投产并形成兼容义务之前，当前默认分支表示有效、可运行、可验证的集成基线，而不是内部实现的永久兼容基线。

应区分：

| 边界 | 原则 |
| :-: | :--: |
| 内部代码结构 | 允许破坏性重构 |
| 开发数据结构 | 无保留义务时可重建；有保留义务时通过 Migration 演进 |
| 外部 API、产品语义、认证授权、生产数据 | 形成承诺后显式兼容和演进 |

高影响、反悔成本较高的决策使用 ADR 记录；局部、可逆的实现决策直接完成。

### 5.4 测试与工程入口

测试按照责任和风险分层：

```text
Domain
→ 单元测试业务规则、不变量和状态变化

Application
→ 使用 Fake / Test Port 验证用例编排

Infrastructure
→ 集成测试真实基础设施接缝

API / Frontend
→ 验证接口、权限和关键交互

End-to-End
→ 少量核心路径
```

仓库提供统一工程入口：

```text
make setup
make dev
make fmt
make lint
make typecheck
make test
make check
```

具体前后端工具可以不同，但本地开发、CI 和自动化统一通过项目级命令执行。`Makefile`
是薄入口。开发环境支持 Linux，以及使用 Linux toolchain 与 Linux filesystem 的
WSL2；不支持原生 Windows / PowerShell runtime。部署与运行目标是 Linux。

### 5.5 工程协作与状态记录

项目的目标、任务、决策和在途状态应记录在 GitHub 或仓库中，不依赖聊天上下文或 Agent 的临时记忆作为唯一信息来源。

| 载体 | 语义 |
| --- | --- |
| Milestone | 当前阶段需要达到的可交付目标 |
| Issue | 明确、可完成、可验证的工作项 |
| Pull Request | 对 Issue 的实际代码变更及验证结果 |
| ADR | 已确定的高影响设计或工程决策 |
| Journal | 跨会话、并行或存在仓外副作用工作的在途记录 |
| `docs/product/deferred.md` | 已识别但当前明确延后的产品或领域设计事项 |
| AGENTS.md | 长期有效的 AI 协作规则与工作入口 |

Issue 应至少明确目标、验收条件和必要约束，并作为具体任务的权威描述；需求变化时应更新 Issue，而不是只保留在聊天记录中。

Journal 仅补充 Issue 和 Git 难以表达的在途状态、影响范围、仓外副作用、回退方式等信息，普通短任务无需额外维护。

开发时优先读取持久化的当前状态：

```text
阶段目标      → Milestone
当前任务      → Open Issue
任务要求      → Issue
当前代码事实  → 当前默认分支
设计决策      → Design Document / ADR
在途状态      → Journal
延后设计      → docs/product/deferred.md
协作规则      → AGENTS.md
```

## 六. 开发与迭代规划

当前开发以 Competition V1 为近期目标，以真实投产为长期目标。开发按垂直切片推进，优先验证核心执行链路，并按切片价值完善复用、协作与产品体验。

### 6.1 开发策略

工程基线和核心执行链路仍优先验证。除真实的接口、数据、权限或集成依赖外，相互独立的能力、接口与可见垂直切片可以并行设计和实现。

前期以后端为主，通过稳定的 API Contract 与前端解耦；前端可以独立推进，并在核心接口稳定后逐步接入。

外部能力通过 Port 隔离。开发和测试阶段允许使用 Fake Implementation，但核心技术边界应尽早替换为真实 PostgreSQL、Git、Shared FS、slurmrestd / Slurm 等实现进行验证。

### 6.2 Walking Skeleton

Walking Skeleton 是系统最先跑通的最薄真实端到端链路，用于验证整体架构和核心技术边界是否成立；它不要求具备完整的产品功能。

```text
HTTP API
   ↓
Application
   ↓
Run + Snapshot
   ↓
Background Worker
   ↓
Load Project Version
   ↓
Materialize to Shared FS
   ↓
Prepare Runtime
(Apptainer / Native)
   ↓
Submit via slurmrestd
   ↓
Slurm
   ↓
Status Update
```

M0 的应用结构验证可以使用 Fake Port；M1 的验收应接入真实 Worker、Git / Shared FS 和 Slurm，以验证核心技术可行性。

### 6.3 Milestone

Milestone 按可交付能力分组，用于表达默认优先级和完成验收，不表示工作启动顺序或全局阶段闸门。具体分组见 6.5 Roadmap。

Template 与 Profile 不作为 Competition V1 的阻塞项；核心链路稳定且时间允许时，可以作为增强能力继续推进。

### 6.4 迭代与范围控制

每个交付切片按照：

```text
Milestone
   ↓
Issue
   ↓
垂直切片
   ↓
Pull Request
   ↓
验证
   ↓
当前默认分支
```

围绕当前可交付切片按需拆分 Issue，不提前固定整个 V1 的全部任务；前序 Milestone 未完成时，无真实依赖的工作仍可启动。

每个 Milestone 只能在自身满足以下条件后声明完成：

- 目标能力能够实际运行；
- 相关验收条件满足；
- 关键路径经过验证；
- `make check` 通过；
- 当前默认分支保持完整、一致、可继续开发。

Roadmap 和 Milestone 可以根据实现反馈调整，但范围变化应显式更新对应记录，不在开发过程中静默扩大目标。

开发早期无保留义务的数据可以重建；进入共享演示、部署或需要保留数据的阶段后，再按照 Migration 和兼容性规则演进。

### 6.5 Roadmap

当前 Roadmap 以 Competition V1 为近期目标，不绑定具体日期，并根据实现反馈持续更新。

| Milestone | 核心目标 | 关键能力 | 默认推进定位 |
| :---: | :---: | :--- | :---: |
| **M0 Engineering Baseline** | 建立可持续开发的工程基线 | Monorepo、Backend、Worker、测试、配置、统一工程入口 | 工程基线优先 |
| **M1 Executable Skeleton** | 跑通最薄真实执行链路 | Run / Snapshot、Worker、Git / Shared FS、slurmrestd / Slurm、状态回写 | 真实链路优先 |
| **M2 Single-user Compute Loop** | 形成单用户完整计算闭环 | User-owned Project / Version、Run Configuration、Run、Log、Artifact | 可见闭环优先 |
| **M3 Reusable Run** | 使已验证计算工作能够复用 | 重跑、Fork、Environment / Shared Resource 校验与不可变版本发布、确定引用 | 随可见切片推进 |
| **M4 Collaborative Reuse** | 支持多人协作与跨 Owner 复用 | User Group / Membership / Role、资产转移、USE Grant、Run Snapshot 引用可用性校验、Resource Entitlement | 随可见切片推进 |
| **M5 Competition V1** | 完成比赛可用产品形态 | 当前支持环境所需身份方案、必要前端、关键异常流程、演示环境与整体收口 | 按交付切片收口 |
| **Optional Enhancement** | 扩展项目创建与场景化复用能力 | Template、Profile... | 核心稳定且时间允许 |

Competition V1 以实际交付的连贯、可见、可运行切片验收，不要求 M0 至 M5 全部完成或按编号顺序推进。每个切片必须声明功能范围、实际运行方式和证据边界；Mock 或 Fake 路径不得作为真实基础设施验证证据。

USTC CAS、更丰富的权限与安全管理可以按切片需要延后；现有服务端对象访问检查和受控演示安全边界仍须保留。

Gallery、资产公共可见性与申请式访问、Official / Featured 策展元数据及 Course Profile 暂不进入当前 Roadmap，继续作为延后设计事项管理。

Competition V1 之后，再根据真实投产需求规划生产级部署与监控、备份恢复、数据迁移、安全加固和长期运维等能力。
