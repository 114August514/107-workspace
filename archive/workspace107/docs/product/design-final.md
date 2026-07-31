# 产品设计最终稿

## 一. 顶级结构

```text
107 Workspace
│
├── 1. 用户、个人入口与全局导航
├── 2. Workspace 协作、成员与权限
├── 3. Project 与项目文件
├── 4. 模板、Fork 与项目复用
├── 5. 运行环境
├── 6. 共享资源与数据
├── 7. 算力与调度配置
├── 8. Run 生命周期与计算执行
├── 9. 日志、运行产物与复现
├── 10. 通知与活动
├── 11. 垂直场景 Profile
├── 12. Workspace 使用与治理
└── 13. 平台管理与运维
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
├── [Core] 登录并识别当前用户
├── [Core] 查看个人基本信息
├── [Core] 查看自己拥有和参与的 Workspace
├── [Core] 查看最近使用的 Workspace
├── [Core] 查看最近使用的 Project
├── [Core] 查看最近提交的 Run
├── [Core] 从个人首页快速进入 Project 或 Run
│
├── [V1] 搜索 Workspace、Project 和 Run
├── [V1] 在多个 Workspace 间切换
├── [V1] 按名称、状态和时间筛选
├── [V1] 置顶常用 Workspace 和 Project
├── [V1] 查看个人最近活动
├── [V1] 查看等待处理的 Workspace 邀请或其他事务
├── [V1] 对接学校统一身份认证
│
├── [V2] 自定义个人首页
├── [V2] 保存常用筛选条件
├── [V2] 个人算力和存储使用概览
│
└── [Future] 个性化工作建议与快捷操作
```

### 2.2 Workspace 协作、成员与权限

Workspace 是 Project 的组织空间，也是成员、权限和资源权益的归属边界。

Workspace 分为：

- Personal Workspace
- Collaborative Workspace

```text
Workspace 空间、成员与资源主体
│
├── A. 通用 Workspace 能力
│   ├── [Core] 查看 Workspace 基本信息
│   ├── [Core] 修改 Workspace 名称和说明
│   ├── [Core] 查看 Workspace 创建人和创建时间
│   ├── [Core] 查看当前用户在 Workspace 中的角色
│   ├── [Core] 查看 Workspace 下的 Project
│   ├── [Core] 查看 Workspace 概览
│   ├── [Core] 查看 Workspace 当前状态
│   │
│   ├── [V1] Workspace 图标和展示信息
│   ├── [V1] Workspace 归档与恢复
│   │
│   ├── [V2] 设置 Workspace 标签
│   ├── [V2] 按标签和状态筛选 Workspace
│   └── [Future] 跨组织迁移 Workspace
│
├── B. Personal Workspace
│   ├── [Core] 进入默认 Personal Workspace
│   └── [V1] 恢复个人 Workspace 的默认配置
│
├── C. Collaborative Workspace
│   ├── [Core] 创建 Collaborative Workspace
│   ├── [Core] 查看成员列表
│   ├── [Core] 邀请成员
│   ├── [Core] 移除成员
│   ├── [Core] 邀请确认与拒绝
│   ├── [Core] 查看成员角色
│   ├── [Core] Owner / Member 基础角色
│   ├── [Core] 成员主动退出 Collaborative Workspace
│   ├── [Core] 转让 Workspace 所有权
│   │
│   ├── [V1] Admin / Viewer 扩展角色
│   ├── [V1] 修改成员角色
│   ├── [V2] 自定义角色
│   ├── [V2] 成员组与批量授权
│   ├── [V2] Project 级细粒度权限
│   └── [Future] 外部协作者与跨组织协作
│
└── D. Workspace 资源申请与资源权益
    ├── [Core] 查看 Workspace 可用资源权益
    ├── [Core] 查看 Workspace 算力使用权限
    ├── [Core] 查看 Workspace 存储配额
    │
    ├── [V1] 申请新增或提升 Workspace 资源权益
    ├── [V1] 查看资源申请审批状态
    ├── [V1] 查看资源申请历史
    ├── [V1] 申请续期
    └── [V1] 主动释放不再需要的资源权益
```

### 2.3 Project 与项目文件

Project 是 Workspace 下可版本化、可运行的计算项目。

```text
Project 与项目文件
│
├── A. Project 基本管理
│   ├── [Core] 在 Workspace 中创建 Project
│   ├── [Core] 查看 Project 基本信息
│   ├── [Core] 修改 Project 名称和说明
│   ├── [Core] 查看 Project 最近更新时间
│   ├── [Core] 查看 Project 当前版本状态
│   ├── [Core] 查看 Project 的 Run 历史入口
│   │
│   ├── [V1] 归档 Project
│   ├── [V1] 恢复已归档 Project
│   ├── [V1] 设置 Project 图标和展示信息
│   │
│   ├── [V2] 设置 Project 标签和分类
│   └── [Future] 跨 Workspace 迁移 Project
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
└── F. Project 运行方案管理
    ├── [Core] 配置默认工作目录和执行命令
    ├── [Core] 查看运行方案的环境、共享资源和算力配置
    ├── [Core] 设置 Project 默认运行方案
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
│   ├── [Core] 从已有 Project 的确定版本创建新 Project
│   ├── [Core] 选择来源 Project Version
│   ├── [Core] 查看来源版本的文件与运行配置概览
│   ├── [Core] 选择目标 Workspace
│   ├── [Core] 设置新 Project 名称和说明
│   ├── [Core] 查看目标 Workspace 可用性检查结果
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
│   ├── [V1] 选择 Project Version 发布为模板
│   ├── [V1] 设置模板名称和简介
│   ├── [V1] 设置模板使用说明
│   ├── [V1] 设置模板分类和标签
│   ├── [V1] 设置模板可见范围
│   ├── [V1] 查看模板对应的来源 Project Version
│   ├── [V1] 查看自己发布的模板
│   ├── [V1] 修改模板展示信息
│   ├── [V1] 发布引用新 Project Version 的模板修订
│   ├── [V1] 查看模板修订历史
│   ├── [V1] 设置当前推荐修订
│   ├── [V1] 弃用模板
│   └── [V1] 取消发布模板
│
├── D. 模板发现与使用
│   ├── [V1] 浏览当前用户可使用的模板
│   ├── [V1] 搜索模板
│   ├── [V1] 按分类和标签筛选模板
│   ├── [V1] 查看模板详情
│   ├── [V1] 查看模板文件概览
│   ├── [V1] 查看模板运行配置概览
│   ├── [V1] 查看模板来源 Project Version
│   ├── [V1] 选择目标 Workspace
│   ├── [V1] 检查目标 Workspace 是否满足使用条件
│   └── [V1] 从模板创建 Project
│
└── E. 模板库治理
    ├── [V1] 发布 Workspace 范围内可见的模板
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

运行环境是供 Project 执行代码时选择的共享运行基础。Workspace 管理可用环境和默认环境，Project 选择实际使用的环境，Run 记录本次执行采用的环境版本。

```text
运行环境
│
├── A. 环境发现与查看
│   ├── [Core] 浏览当前 Workspace 可使用的运行环境
│   ├── [Core] 查看运行环境详情
│   ├── [Core] 查看运行环境的可用版本
│   │
│   ├── [V1] 搜索和筛选运行环境
│   ├── [V1] 查看环境版本更新说明
│   ├── [V2] 比较不同环境及其版本
│   └── [Future] 根据 Project 推荐运行环境
│
├── B. Workspace 默认环境
│   ├── [Core] 查看 Workspace 默认环境
│   ├── [Core] 设置或修改 Workspace 默认环境
│   ├── [Core] 查看 Workspace 下各 Project 的环境使用情况
│   │
│   ├── [V1] 查看修改默认环境的影响范围
│   └── [V1] 查看默认环境变更历史
│
├── C. Project 环境选择
│   ├── [Core] 查看 Project 当前有效环境
│   ├── [Core] 使用 Workspace 默认环境
│   ├── [Core] 显式选择其他可用环境及版本
│   ├── [Core] 切换回 Workspace 默认环境
│   ├── [Core] 在发起 Run 前确认实际环境
│   │
│   ├── [V1] 检查 Project 与环境的基础兼容性
│   ├── [V1] 查看环境不可用或不兼容的原因
│   └── [V2] 保存多个环境选择预设
│
├── D. 环境创建与版本管理
│   ├── [V1] 在 Workspace 中创建运行环境
│   ├── [V1] 配置环境定义
│   ├── [V1] 创建和发布环境版本
│   ├── [V1] 查看环境准备状态和日志
│   ├── [V1] 管理环境版本
│   ├── [V1] 弃用或归档环境
│   │
│   ├── [V2] 从已有环境派生新环境
│   ├── [V2] 导入和导出环境定义
│   ├── [V2] 比较环境版本差异
│   └── [Future] 根据 Project 依赖自动创建环境
│
└── E. 环境共享与使用管理
    ├── [V1] 查看环境的可用范围
    ├── [V1] 授权其他 Workspace 使用环境
    ├── [V1] 查看和管理环境授权
    ├── [V1] 查看引用环境的 Project 和近期 Run
    ├── [V1] 查看环境当前是否可用
    │
    ├── [V2] 申请和审批受限环境的使用权
    ├── [V2] 设置环境授权有效期
    ├── [V2] 查看环境使用统计
    └── [V2] 查看兼容性和安全检查结果
```

### 2.6 共享资源与数据

共享资源是独立于 Project 存在、由 Workspace 或平台拥有并授权使用、可被多个 Project 引用的版本化内容。

```text
共享资源与数据
│
├── A. 资源发现与查看
│   ├── [Core] 浏览当前 Workspace 可发现的共享资源
│   ├── [Core] 查看共享资源详情和使用说明
│   ├── [Core] 查看共享资源的可用版本
│   ├── [Core] 查看当前 Workspace 对资源的可用状态
│   │
│   ├── [V1] 搜索和筛选共享资源
│   ├── [V1] 预览资源目录、样例或结构信息
│   ├── [V2] 比较不同资源版本
│   └── [Future] 根据 Project 推荐共享资源
│
├── B. Project 资源关联
│   ├── [Core] 查看 Project 已关联的共享资源
│   ├── [Core] 为 Project 关联可使用的资源版本
│   ├── [Core] 配置资源在 Project 中的访问位置
│   ├── [Core] 更换 Project 关联的资源版本
│   ├── [Core] 解除 Project 与共享资源的关联
│   ├── [Core] 查看资源关联的当前状态
│   │
│   └── [V1] 查看资源不可用的原因和处理方式
│
├── C. 资源创建与版本管理
│   ├── [Core] 在 Workspace 中创建共享资源
│   ├── [Core] 设置和修改资源基本信息及使用说明
│   ├── [Core] 上传文件或目录形成首个资源版本
│   ├── [Core] 查看资源版本及其准备和发布状态
│   ├── [Core] 上传并发布新的资源版本
│   │
│   ├── [V1] 设置资源的默认推荐版本
│   ├── [V1] 填写和查看版本更新说明
│   ├── [V1] 从外部存储导入共享资源
│   ├── [V1] 将 Project 文件或目录发布为共享资源
│   ├── [V1] 将 Project 文件或目录发布为新的资源版本
│   ├── [V1] 将 Run Artifact 发布为共享资源或新版本
│   ├── [V1] 用共享资源引用替换 Project 中的原始内容
│   ├── [V1] 弃用资源版本
│   ├── [V1] 归档和恢复共享资源
│   │
│   ├── [V2] 比较不同资源版本的内容
│   ├── [V2] 从已有资源版本派生新资源
│   └── [Future] 与外部数据源保持版本同步
│
├── D. 资源共享与权限管理
│   ├── [Core] 查看资源所有者和当前共享范围
│   ├── [Core] 查看当前 Workspace 对资源的权限
│   │
│   ├── [V1] 将共享资源授权给指定 Workspace 使用
│   ├── [V1] 查看和管理资源授权
│   ├── [V1] 撤销 Workspace 的资源使用权
│   ├── [V1] 查看资源授权变更记录
│   │
│   ├── [V2] 提交资源的平台公共发布申请
│   ├── [V2] 查看公共发布审核状态
│   ├── [V2] 停止公开或弃用公共资源
│   ├── [V2] 将资源设置为可发现但需要申请
│   ├── [V2] 申请和审批受限资源的使用权
│   ├── [V2] 设置资源授权有效期
│   ├── [V2] 管理资源下载和导出策略
│   │
│   └── [Future] 跨平台共享资源
│
└── E. 引用与使用追踪
    ├── [V1] 查看引用共享资源的 Project
    ├── [V1] 查看使用指定资源版本的近期 Run
    ├── [V1] 查看弃用、归档或撤权的影响范围
    │
    ├── [V2] 查看共享资源使用统计
    └── [V2] 查看资源来源和派生关系
```

### 2.7 算力与调度配置

Workspace 决定可使用的算力权益，Project 保存默认资源配置，Run 确定本次资源请求，底层调度系统负责真正的排队与分配。

```text
算力与调度配置
│
├── A. Project 算力配置
│   ├── [Core] 查看当前 Workspace 可使用的算力方案
│   ├── [Core] 查看算力方案的资源内容和限制
│   ├── [Core] 在可用算力方案之间切换
│   └── [Core] 查看方案不可用的原因
│
├── B. 高级资源与调度配置
│   ├── [V1] 切换到高级配置模式
│   ├── [V1] 配置节点数量
│   ├── [V1] 配置 CPU 和内存需求
│   ├── [V1] 配置 GPU 数量
│   ├── [V1] 配置最长运行时间
│   ├── [V1] 选择当前可用的调度账户
│   ├── [V1] 选择当前可用的分区
│   ├── [V1] 选择当前可用的 QoS
│   ├── [V1] 将部分参数保留为自动选择
│   ├── [V1] 查看配置对应的资源总量
│   ├── [V1] 将高级配置保存到 Project 运行方案
│   ├── [V2] 从超出权益的资源请求发起资源权益申请
│   └── [V2] 在权益获批后恢复原资源配置
│
└── C. 调度请求解析与校验
    ├── [Core] 查看本次 Run 最终的资源请求
    ├── [Core] 检查资源请求是否符合 Workspace 权益
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

Run 是 Project 的一次不可变执行记录。平台在创建 Run 时固定代码快照、运行配置、环境、共享资源和算力请求，并将任务提交给底层调度系统执行。

```text
Run 生命周期与计算执行
│
├── A. Run 创建与提交
│   ├── [Core] 从 Project 发起 Run
│   ├── [Core] 选择或使用 Project 默认运行方案
│   ├── [Core] 查看并调整本次 Run 的工作目录和执行命令
│   ├── [Core] 确认本次 Run 的代码快照和完整执行配置
│   ├── [Core] 执行提交前检查并查看阻止提交的问题
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
│   ├── [Core] 使用相同代码快照和配置重新运行
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
│   ├── [Core] 从 Run 进入对应的 Project 版本
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
└── 创建人与创建时间
```

### 2.9 日志、运行产物与复现

本节负责呈现 Run 执行过程中产生的信息和结果，并保存足以解释、比较和复现该 Run 的证据。

```text
日志、运行产物与复现
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
    ├── [Core] 查看 Run 使用的代码、命令和工作目录
    ├── [Core] 查看 Run 使用的环境和共享资源版本
    ├── [Core] 查看 Run 使用的算力与调度配置
    ├── [Core] 查看 Run 的退出状态和关键执行信息
    │
    ├── [V1] 导出 Run 复现清单
    ├── [V1] 查看复现所需依赖当前是否仍然可用
    └── [Future] 导出可移植的完整复现包
```

### 2.10 通知与活动

本节负责把与用户相关的重要变化及时呈现出来，并提供面向协作的近期活动记录。

> 注意：
>
> ```text
> 通知
> → 面向特定用户，需要用户关注或处理
>
> 活动
> → 面向 Workspace 或 Project，说明最近发生了什么 
> ```
>

```text
通知与活动
│
├── A. 通知中心
│   ├── [Core] 查看与当前用户相关的通知
│   ├── [Core] 查看未读通知数量
│   ├── [Core] 查看通知类型、时间和来源对象
│   ├── [Core] 从通知进入对应的 Run、Project、Workspace 或资源
│   ├── [Core] 将通知标记为已读或未读
│   └── [Core] 批量标记通知为已读
│       │
│       ├── [V1] 按类型和时间筛选通知
│       ├── [V1] 搜索通知
│       └── [V1] 归档或删除历史通知
│
├── B. 重要事件通知
│   ├── [Core] 接收自己发起的 Run 结束或异常通知
│   ├── [Core] 接收 Workspace 成员和权限变更通知
│   ├── [Core] 接收影响当前 Project 的环境或共享资源不可用通知
│   ├── [Core] 接收平台维护和服务异常通知
│   │
│   ├── [V1] 接收 Run 开始运行通知
│   ├── [V1] 接收共享资源版本弃用、归档或授权撤销通知
│   ├── [V1] 接收环境版本弃用或可用性变化通知
│   ├── [V1] 接收配额接近上限和生命周期提醒
│   └── [V2] 订阅指定 Project、Run 或资源的变化
│
├── C. 通知偏好与送达
│   ├── [Core] 在平台内接收通知
│   ├── [Core] 按通知类别启用或关闭非强制通知
│   ├── [Core] 查看不可关闭的重要系统通知
│   │
│   ├── [V1] 通过邮件接收重要通知
│   ├── [V1] 分别配置站内和邮件通知偏好
│   ├── [V1] 设置免打扰时段
│   ├── [V1] 接收每日或每周通知摘要
│   ├── [V2] 按 Workspace 或 Project 配置通知偏好
│   └── [Future] 接入更多外部消息渠道
│
└── D. Workspace 与 Project 活动
    ├── [Core] 查看 Workspace 的近期活动
    ├── [Core] 查看 Project 的近期活动
    ├── [Core] 查看活动的操作者、时间、对象和动作
    ├── [Core] 从活动记录进入对应对象
    │
    ├── [V1] 按成员、对象类型和时间筛选活动
    ├── [V1] 查看与自己相关的活动
    ├── [V1] 查看 Project 派生、版本和运行方案变更活动
    ├── [V1] 查看环境、共享资源和成员权限变更活动
    └── [V2] 订阅指定对象的活动更新
```

### 2.11 垂直场景 Profile

为 Workspace 启用和配置可复用的垂直场景能力，并通过 Course Profile 等具体实现，将平台基础能力编排为完整业务工作流。

```text
垂直场景 Profile
│
├── A. Profile 发现与启用
│   ├── [V1] 浏览平台支持的垂直场景 Profile
│   ├── [V1] 查看 Profile 提供的角色、能力和适用范围
│   ├── [V1] 查看启用 Profile 所需的 Workspace 条件
│   ├── [V1] 为符合条件的 Workspace 启用 Profile
│   ├── [V1] 完成 Profile 的初始化配置
│   ├── [V1] 停用 Profile 并查看对场景对象的影响
│   │   └── [V2] 迁移或导出停用前的 Profile 配置
│   │
│   └── [V1] 查看 Workspace 当前启用的 Profile 和状态
│       │
│       ├── [V2] 查看 Profile 版本和更新说明
│       ├── [V2] 升级 Workspace 使用的 Profile
│       └── [Future] 组合多个兼容的 Profile
│
├── B. Profile 配置与复用
│   ├── [V1] 配置场景名称、说明和生命周期信息
│   ├── [V1] 配置场景角色及其基础权限范围
│   ├── [V1] 配置场景提供、推荐或授权使用的环境、资源和算力规则
│   ├── [V1] 配置场景工作流的默认规则
│   ├── [V1] 查看和修改当前 Workspace 的 Profile 配置
│   ├── [V1] 基于已有 Workspace 的 Profile 配置创建新 Workspace
│   └── [V1] 选择需要复用和排除的场景配置
│       │
│       ├── [V2] 保存可重复使用的 Profile 配置预设
│       ├── [V2] 比较两个 Workspace 的 Profile 配置
│       └── [V2] 查看 Profile 配置变更历史
│
├── C. Profile 场景体验
│   ├── [V1] 根据场景角色展示对应的工作入口
│   ├── [V1] 查看与当前用户相关的场景任务和状态
│   ├── [V1] 按 Profile 工作流执行场景操作
│   ├── [V1] 从场景对象进入当前用户有权访问的 Project、Run 或资源
│   ├── [V1] 查看 Workspace 的场景生命周期状态
│   └── [V1] 接收 Profile 产生的场景通知
│
└── D. Course Profile
    ├── [V1] 配置课程信息以及教师、助教和学生角色
    ├── [V1] 创建和发布 Assignment
    ├── [V1] 使用确定的 Project Version 作为 Assignment 起始内容
    ├── [V1] 配置 Assignment 的说明、时间和提交要求
    ├── [V1] 配置 Assignment 推荐使用的环境、共享资源和算力方案
    ├── [V1] 学生查看可参与的 Assignment
    ├── [V1] 学生将 Assignment 起始内容 Fork 到 Personal Workspace
    ├── [V1] 学生在 Personal Workspace 中独立编辑 Project 和创建 Run
    ├── [V1] 查看 Assignment 的开始、提交和截止状态
    ├── [V1] 学生显式提交确定的 Project Version 快照
    ├── [V1] 保留和查看多次 Submission 记录
    ├── [V1] 教师和助教查看及管理 Submission 快照
    └── [V1] 关闭、归档和复用课程配置
        │
        ├── [V2] 提交选定的 Artifact 或 Run 结果摘要
        ├── [V2] 对 Submission 提供反馈
        ├── [V2] 对 Submission 快照发起受信任的自动评测
        ├── [V2] 学生分组与分组作业
        ├── [V2] 个别延期、宽限期和迟交规则
        └── [Future] 与外部教学和成绩系统集成
```

### 2.12 Workspace 使用与治理

面向 Workspace 管理员，负责查看和治理归属于当前 Workspace 的对象、存储和资源使用，以及当前 Workspace 明确提供或承担的额度。

```text
Workspace 使用与治理
│
├── A. Workspace 使用概览
│   ├── [Core] 查看归属于当前 Workspace 的主要数据和资源使用量
│   ├── [Core] 查看当前 Workspace 的额度上限和剩余量
│   ├── [Core] 查看当前操作受到的配额、并发或容量限制
│   ├── [Core] 查看因额度或限制无法完成操作的原因
│   ├── [Core] 查看 Project、Run、日志、Artifact 和共享资源的主要占用
│   │
│   ├── [V1] 按 Project、资源类型和时间查看使用量
│   ├── [V1] 查看使用趋势和额度预警
│   └── [V2] 为 Project 或成员设置 Workspace 内部使用预算
│
├── B. Workspace 数据保留与清理
│   ├── [Core] 查看当前 Workspace 中数据的保留和到期状态
│   ├── [Core] 清理不再需要的 Run 日志和 Artifact
│   ├── [Core] 查看即将到期或被自动清理的数据
│   ├── [Core] 将重要 Run 或 Artifact 标记为保留
│   ├── [Core] 删除或清理前查看关联对象和影响范围
│   │
│   ├── [V1] 批量清理历史日志和 Artifact
│   ├── [V1] 配置 Workspace 的数据保留策略
│   ├── [V1] 查看自动清理结果
│   └── [V2] 为特定对象设置长期保留或清理豁免
│
├── C. Workspace 凭据与外部访问
│   ├── [V1] 创建和管理 Workspace 凭据
│   ├── [V1] 将凭据授权给指定 Project 或运行方案
│   ├── [V1] 在 Run 中引用凭据而不展示明文
│   ├── [V1] 更新、轮换和撤销凭据
│   ├── [V1] 查看凭据被哪些 Project 或运行方案引用
│   ├── [V1] 查看凭据失效或即将过期状态
│   └── [V2] 配置网络和外部服务访问策略
│
├── D. Workspace 授权额度使用
│   ├── [V1] 查看由当前 Workspace 提供或承担的算力额度使用情况
│   ├── [V1] 查看额度被哪些 Project、成员或场景消耗
│   ├── [V1] 查看额度剩余量和有效期限
│   ├── [V1] 查看因授权额度耗尽而受影响的操作
│   └── [V2] 配置成员、Project 或场景的内部额度上限
│
└── E. Workspace 管理审计
    ├── [V1] 查看当前 Workspace 内的关键管理操作
    ├── [V1] 查看操作人、时间、对象、动作和结果
    ├── [V1] 查看成员、角色、权限和资源授权变更
    ├── [V1] 查看对象删除、恢复、保留和清理记录
    ├── [V1] 查看 Run 取消、强制终止和管理员干预记录
    └── [V1] 按操作人、对象、动作和时间筛选审计记录
        │
        └── [V2] 导出审计记录和治理报告
```

### 2.13 平台管理与运维

面向平台管理员，负责管理整个 107 平台的用户与 Workspace、计算集群、平台级资源目录、全局策略以及运行故障。

> 平台管理员需要管理：
>
> ```text
> 平台
> ├── 用户与 Workspace 状态
> ├── 集群和调度资源
> ├── 平台环境与公共资源
> ├── 全局配额和生命周期策略
> └── 服务健康、故障与审计
> ```

```text
平台管理与运维
│
├── A. 平台运行概览
│   ├── [V1] 查看平台、集群和关键服务的运行状态
│   ├── [V1] 查看节点、CPU、内存、GPU 和存储容量概览
│   ├── [V1] 查看运行中、排队中和异常任务数量
│   ├── [V1] 查看各分区的资源使用率、排队压力和可用状态
│   ├── [V1] 查看当前告警、故障和维护事件
│   │
│   ├── [V2] 查看资源使用趋势、历史峰值和服务质量
│   └── [Future] 查看容量预测和扩容建议
│
├── B. 集群与调度资源管理
│   ├── [V1] 查看和管理平台接入的计算集群
│   ├── [V1] 查看节点、分区及其资源和运行状态
│   ├── [V1] 将集群、分区或节点设为维护、停用或恢复可用
│   ├── [V1] 控制集群或分区是否接收新的 Run
│   ├── [V1] 管理平台算力规格及其底层调度映射
│   ├── [V1] 管理 Account、Partition 和 QoS 的合法组合
│   │
│   ├── [V2] 管理资源预约、专用算力池和特殊硬件
│   └── [Future] 管理多集群路由和跨集群调度
│
├── C. 全局任务运维
│   ├── [V1] 查看和筛选全平台 Run 与底层调度任务
│   ├── [V1] 查看 Run 与调度 Job 的对应关系
│   ├── [V1] 查看任务请求、实际分配、排队原因和异常状态
│   ├── [V1] 查看长时间排队、长时间运行和异常占用任务
│   ├── [V1] 取消或终止需要管理员干预的任务
│   ├── [V1] 记录管理员干预原因和执行结果
│   │
│   ├── [V2] 批量处置异常或积压任务
│   └── [V2] 对符合条件的任务执行挂起、恢复或重新排队
│
├── D. 用户与 Workspace 支持
│   ├── [V1] 搜索和查看平台用户及 Workspace
│   ├── [V1] 查看用户和 Workspace 的状态、权益及主要用量
│   ├── [V1] 停用和恢复异常用户或 Workspace
│   ├── [V1] 处理 Workspace 所有权和访问异常
│   ├── [V1] 配置 Workspace 的算力、存储和并发额度
│   ├── [V1] 查看用户或 Workspace 无法提交 Run 的平台侧原因
│   ├── [V1] 审批用户申请的资源权益
│   │
│   └── [V2] 批量处理用户、Workspace 和资源权益
│
├── E. 平台资源与全局策略
│   ├── [V1] 管理平台提供的运行环境及其版本
│   ├── [V1] 管理平台公共共享资源
│   ├── [V1] 管理 Project 模板和垂直场景 Profile 目录
│   ├── [V1] 审核和处置公共发布内容
│   ├── [V1] 配置平台默认额度、资源上限和保留策略
│   ├── [V1] 配置公开发布、外部导入和访问安全规则
│   ├── [V1] 查看策略或资源变更的影响范围
│   ├── [V1] 查看认证、Slurm、存储、Git、通知和监控等平台集成状态
│   │
│   ├── [V2] 管理策略例外、服务等级和资源保障
│   ├── [V2] 管理 Profile 版本、兼容性和升级范围
│   └── [Future] 管理跨组织和跨集群公共资源目录
│
└── F. 告警、故障与平台审计
    ├── [V1] 查看和处理平台告警
    ├── [V1] 创建并跟踪平台故障事件
    ├── [V1] 查看故障影响的集群、Workspace 和 Run
    ├── [V1] 发布、更新和撤回维护或故障公告
    ├── [V1] 查看平台管理员的关键操作记录
    ├── [V1] 搜索和筛选管理员操作及干预记录
    │
    ├── [V2] 导出平台运维和审计记录
    └── [Future] 生成自动化故障复盘和容量治理报告
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
| Workspace | 成员、权限、Project、资源权益和治理规则的归属边界 |
| Personal Workspace | 默认由单个用户拥有和管理的 Workspace |
| Collaborative Workspace | 由多个成员按照角色共同使用的 Workspace |
| Membership | User 在 Workspace 中的身份 (决定了在本 Workspace 能做的操作) |
| Workspace Asset Grant | 某个 Workspace 获得使用其他 Workspace 或平台资产的权限 |

`Membership` 的结构入下：

```text
Membership
├── User
├── Workspace
├── Role
└── Status
```

值得说明的是，Course 不构成第三种 Workspace 类型。

```text
Course Workspace
=
启用了 Course Profile 的 Collaborative Workspace
```

Profile 不改变 Workspace 的基础归属和权限边界。

#### 3.1.2 Project 与版本

| 中文名称 | 英文名称 | 定义 |
| :----- | :---- | :--- |
| Project | Project | Workspace 下可编辑、可版本化、可运行的计算项目 |
| Project 当前状态 | Project Working State | Project 当前可编辑的文件和目录状态 |
| Project 版本 | Project Version | Project 在某个时刻正式保存的不可变内容快照 |
| 分支 | Project Branch | 指向某个 Project Version 的可变开发引用 |
| 运行方案 | Run Configuration | Project 下可编辑、可命名、可复用的执行配置 |
| 派生关系 | Fork Relation | 新 Project 与来源 Project Version 之间的来源记录 |
| 模板 | Template | 对可复用 Project Version 的可发现目录入口 |
| 模板修订 | Template Revision | 模板在某次发布时固定引用的 Project Version |

#### 3.1.3 运行环境、内容资源与输入

| 中文名称 | 英文名称 | 定义 |
| :--- | :--- | :--- |
| 运行环境 | Environment | 可被多个 Project 选择和复用的独立运行基础 |
| 环境版本 | Environment Version | 某个 Environment 已发布的不可变版本 |
| 共享资源 | Shared Resource | 独立于 Project 存在，可版本化、授权和长期管理的内容资源 |
| 共享资源版本 | Shared Resource Version | Shared Resource 已发布的不可变内容版本 |
| Artifact | Artifact | 某次 Run 产生并被保存的不可变结果 |
| 确定内容 | Content Version | 具有稳定内容身份、不会原地变化的文件、文件集合或目录快照 |
| 输入绑定 | Input Binding | 将一份确定内容绑定到 Run 中指定访问路径的关系 |
| 输入访问路径 | Input Access Path | 确定内容在 Run 执行环境中暴露的文件或目录路径 |

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

创建 Run 时，平台必须将 Run Configuration 中的 Input Binding 解析为当前有权使用的确定内容，并固定到 Run Snapshot 中。后续来源对象的授权或可用状态发生变化，不得改变已经形成的 Run Snapshot。

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
| 配置变量 | Variable | 由 Workspace 管理、可直接查看和引用的非敏感键值配置 |
| Secret | Secret | 由 Workspace 安全保存、用于存储 Token、密码和密钥等敏感信息的键值配置 |
| 环境变量 | Environment Variable | 由 Run Configuration 定义，并在 Run 执行时提供给用户程序的键值配置 |

Variable 和 Secret 属于 Workspace，环境变量属于 Run Configuration，并在 Run 执行时生效：

```text
Workspace
├── Variables
│   ├── LOG_LEVEL = INFO
│   └── MODEL_NAME = resnet50
│
└── Secrets
    ├── HF_TOKEN
    └── WANDB_API_KEY

Project
└── Run Configuration
    └── Environment Variables
```

Variables 用于保存非敏感配置，Secrets 用于保存密码、Token 和密钥等敏感信息。Secret 只有在 Run Configuration 中被明确引用时，才会提供给对应的 Run。

Run Configuration 使用与 GitHub Actions 类似的表达式引用 Variable 和 Secret：

```yaml
env:
  LOG_LEVEL: ${{ vars.LOG_LEVEL }}
  BATCH_SIZE: "32"
  HF_TOKEN: ${{ secrets.HF_TOKEN }}
  WANDB_API_KEY: ${{ secrets.WANDB_API_KEY }}
```

其中：

```text
Literal Value
→ 直接保存在 Run Configuration 中

${{ vars.LOG_LEVEL }}
→ 引用 Workspace Variable

${{ secrets.HF_TOKEN }}
→ 引用 Workspace Secret

env
→ 指定最终提供给程序的环境变量名称
```

因此，Variable 或 Secret 的名称不必与最终的环境变量名称相同：

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

创建 Run 时：

```text
普通值和 Variable
→ 解析后固定到 Run Snapshot

Secret
→ Run Snapshot 只保存引用表达式
→ 不保存 Secret 明文
→ 执行 Run 时由平台安全提供
```

Variable 和 Secret 应遵守以下规则：

```text
1. 非敏感配置使用 Variables，敏感信息使用 Secrets。
2. Project 文件和 Run Configuration 不得保存 Secret 明文。
3. Secret 必须在 Run Configuration 中显式引用后才能被 Run 使用。
4. Run Snapshot、日志和页面不得展示 Secret 明文。
5. 创建 Run 时，平台必须检查引用的 Variable 和 Secret 是否存在且可用。
6. Fork 或使用模板时，可以复制引用表达式，但不能复制源 Workspace 的 Secret。
7. 目标 Workspace 缺少相应 Variable 或 Secret 时，Run Configuration 应显示为未解析状态。
```

最终领域关系就是：

```text
Workspace
├── Variable
└── Secret

Run Configuration
└── Environment Variables
    ├── Literal Value
    ├── ${{ vars.NAME }}
    └── ${{ secrets.NAME }}
        ↓ 创建 Run

Run Snapshot
└── 已固定的环境变量配置
```

#### 3.1.5 算力、权益与调度

| 中文名称 | 英文名称 | 定义 |
| :------ | :----- | :--- |
| 算力方案 | Compute Plan | 平台面向用户提供的命名资源与运行限制组合 |
| 资源权益 | Resource Entitlement | Workspace 获得的算力方案使用资格及其有效期限 |
| 权益申请 | Entitlement Request | Workspace 请求开通、调整或延长资源权益的申请记录 |
| 算力请求 | Compute Request | Run Configuration 为一次运行声明的具体资源需求 |
| 调度映射 | Scheduler Mapping | 将算力方案和算力请求转换为底层调度参数的平台规则 |
| 已解析调度配置 | Resolved Scheduler Configuration | 创建 Run 时解析并固定的最终调度与资源参数 |
| 资源使用记录 | Resource Usage Record | Run 执行产生的资源分配、运行时长、运行状态及可观测使用情况 |

权益申请审核通过后，形成或更新 Workspace 的资源权益：

```text
Entitlement Request
        ↓ 审核通过
Resource Entitlement
        ↓
Workspace 可以使用相应的 Compute Plan
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
        +
Scheduler Mapping
        ↓
Resolved Scheduler Configuration
        ↓
提交并执行 Run
        ↓
Resource Usage Record
```

各概念分别回答：

```text
Resource Entitlement
→ Workspace 有权使用哪些算力方案

Compute Plan
→ 平台向用户提供什么算力方案

Compute Request
→ 本次运行具体需要多少资源

Scheduler Mapping
→ 平台如何转换为底层调度参数

Resolved Scheduler Configuration
→ 本次 Run 最终使用什么调度与资源参数

Resource Usage Record
→ 本次 Run 实际分配了什么资源、运行了多久
```

应遵守以下规则：

```text
1. Workspace 只能使用其 Resource Entitlement 允许的 Compute Plan。

2. Compute Request 必须符合所选 Compute Plan 的资源范围和运行限制。

3. Scheduler Mapping 由平台管理，普通用户不直接配置底层调度参数。

4. Resolved Scheduler Configuration 在创建 Run 时固定到 Run Snapshot；
   后续权益、算力方案或映射规则变化不得改变已有 Run。

5. Resource Usage Record 用于运行详情、故障定位和平台运维。

6. Entitlement Request 是申请记录；
   只有审核通过后形成的 Resource Entitlement 才代表有效使用资格。
```

底层实现不在本章涉及。

#### 3.1.6 Run 与执行过程

| 中文名称 | 英文名称 | 定义 |
| :------ | :----- | :--- |
| Run | Run | Project 基于确定版本和运行配置创建的一次独立执行实例 |
| Run 快照 | Run Snapshot | Run 创建时固定、用于执行和复现的不可变配置记录 |
| 调度任务 | Scheduler Job | Run 提交后由底层调度系统创建和执行的任务 |
| 日志 | Log | Run 执行过程中产生的标准输出、标准错误和平台执行事件 |
| Artifact 收集规则 | Artifact Collection Rule | 指定 Run 执行结束后，将哪些输出文件或目录保存为 Artifact 的配置 |
| 指标 | Metric | Run 可选上报的结构化数值结果或时间序列，用于结果展示和运行对比 |

Run Configuration 是 Project 下可编辑、可复用的运行方案，包括：

```text
Run Configuration
├── Working Directory
├── Command
├── Environment
├── Input Bindings
├── Environment Variables
├── Compute Plan
├── Compute Request
└── Artifact Collection Rules
```

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
    └── 用于实际执行、历史查看和复现
```

Run 创建后，包含来源信息、不可变执行快照和可变化的执行信息：

```text
Run
├── 来源信息
│   ├── Project
│   ├── Source Run Configuration
│   ├── Created By
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

应遵守以下规则：

```text
1. Run Configuration 可以编辑和复用，
   但修改不得影响已经创建的 Run。

2. 创建 Run 时，平台必须将执行所需的可变引用
   解析为确定版本、确定内容或确定配置。

3. 每个 Run 必须拥有独立的 Run Snapshot；
   执行时不得重新读取当前 Run Configuration。

4. Run Snapshot 创建后不得修改。

5. Run Snapshot 不得保存 Secret 明文；
   Secret 只固定引用关系，并在执行时由平台安全提供。

6. 平台先创建 Run 并固定 Run Snapshot，
   再向底层调度系统提交任务；
   提交成功后，Run 才关联对应的 Scheduler Job。

7. Run 状态、执行时间和调度任务信息
   可以随执行过程更新。

8. Log、Metric、Artifact 和 Resource Usage Record
   均由 Run 执行产生，不属于 Run Snapshot。

9. Metric 是可选结果，并非每个 Run 都必须上报。

10. 用户重新运行时必须创建新的 Run 和 Run Snapshot，
    不能修改或重新启动原有 Run。
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
| Profile | Profile | 将平台基础能力、默认配置和工作流组合为特定使用场景的扩展定义 |
| Profile 版本 | Profile Version | 某个 Profile 已发布的不可变版本 |
| Profile 实例 | Profile Instance | 某个 Workspace 启用确定 Profile Version 后形成的场景配置 |

Profile 是建立在平台基础领域模型之上的场景扩展机制：

```text
Profile
├── 组合平台基础能力
├── 提供场景工作流
├── 提供默认配置
├── 提供场景导航与界面
└── 可以引入场景专属对象
```

Workspace 启用 Profile 时，应形成对应的 Profile Instance：

```text
Workspace
└── Profile Instance
    └── Profile Version
```

Profile 与 Workspace 类型是不同概念：

```text
Workspace
→ 成员、权限、资源和对象的归属边界

Profile
→ Workspace 中启用的场景能力和工作流
```

Profile 必须遵守以下规则：

```text
1. Profile Instance 必须属于一个 Workspace。

2. Profile Instance 必须引用确定的 Profile Version。

3. Profile Version 发布后不得原地修改；
   Profile 发生变化时应发布新版本。

4. Profile 可以组合基础能力并引入场景专属对象，
   但不能改变 Workspace、Project、Run 等基础对象的归属关系。

5. Profile 不能绕过平台既有的权限、版本不可变性和执行隔离规则。

6. Profile Version 更新后，不应静默改变已有 Profile Instance；
   是否升级应由平台按照明确规则处理。
```

---

### 3.2 核心对象关系

#### 3.2.1 核心对象图

```text
User
└── Membership
    └── Workspace
        ├── Project
        │   ├── Project Working State
        │   ├── Project Version
        │   ├── Run Configuration
        │   └── Run
        │       ├── Run Snapshot
        │       ├── Log
        │       ├── Artifact
        │       ├── Metric
        │       └── Resource Usage Record
        │
        ├── Variable
        ├── Secret
        ├── Resource Entitlement
        └── Profile Instance
```

#### 3.2.1 User

```text
对象名称：
User

定义：
平台中的自然人身份。

主要关系：
├── 拥有一个默认 Personal Workspace
├── 可以参与多个 Collaborative Workspace
├── 通过 Membership 获得 Workspace 角色
├── 可以创建 Project Version、Run 和其他对象
└── 可以成为管理操作和审计记录的操作者

可变信息：
姓名、头像、联系方式和用户偏好。

不可变或外部确定信息：
平台用户标识、身份来源。
```

User 本身不是 Project、Run 或资源的直接所有权边界。

用户创建的对象原则上归属于操作发生时所在的 Workspace。

---

### 3.2.2 Workspace

```text
对象名称：
Workspace

定义：
成员、权限、Project、资源权益、凭据和治理规则的归属边界。

类型：
├── Personal Workspace
└── Collaborative Workspace

主要关系：
├── 包含 Project
├── 拥有 Membership
├── 持有 Resource Entitlement
├── 管理 Workspace Credential
├── 可以拥有 Environment
├── 可以拥有 Shared Resource
├── 可以接受其他 Workspace 的资源授权
└── 可以启用 Profile Instance

可变性：
名称、说明、成员、角色、默认环境和治理配置可修改。

生命周期：
Active → Archived → Closed
```

Personal Workspace 与 Collaborative Workspace 共享同一套基础对象模型，差异主要体现在成员和管理方式。

```text
Personal Workspace
→ 默认只有所属用户管理

Collaborative Workspace
→ 通过 Membership 和 Role 管理多个成员
```

---

### 3.2.3 Membership

```text
对象名称：
Membership

定义：
User 与 Collaborative Workspace 之间的成员关系。

主要属性：
├── User
├── Workspace
├── Role
├── Membership Status
├── 加入时间
└── 邀请与处理信息

可变性：
角色和状态可以改变。

生命周期：
Invited → Active → Left / Removed
```

User 加入某个 Workspace，只获得该 Workspace 范围内的权限。

Membership 不会传播到用户的 Personal Workspace 或其他 Collaborative Workspace。

---

### 3.2.4 Project

```text
对象名称：
Project

定义：
Workspace 下可编辑、可版本化、可运行的计算项目。

归属：
必须且只能属于一个 Workspace。

主要关系：
├── Project Working Tree
├── Project Branch
├── Project Version
├── Run Configuration
├── Run
└── Fork Relation

可变性：
Project 基本信息、当前文件和运行方案可修改。

生命周期：
Active → Archived
```

Project 是可持续演化的工作对象，不是不可变快照。

Project 的当前内容和历史版本必须区分。

---

### 3.2.5 Project Working Tree

```text
对象名称：
Project Working Tree

定义：
Project 当前可编辑的文件和目录状态。

归属：
属于一个 Project。

可变性：
可以上传、编辑、移动、复制和删除文件。

与版本关系：
保存 Project Version 时，对当前内容形成不可变快照。
```

Project Working Tree 不等于 Workspace，也不等于 Project Version。

---

### 3.2.6 Project Version

```text
对象名称：
Project Version

定义：
Project 在确定时刻保存的不可变内容版本。

归属：
属于一个 Project。

产生方式：
├── 用户保存当前 Project 内容
├── 合并分支产生新版本
└── 其他明确的版本保存操作

可变性：
创建后不可修改。

主要用途：
├── 创建 Run
├── Fork 新 Project
├── 发布模板修订
├── 作为 Assignment 起始内容
└── 创建 Submission
```

Project Version 被归档或源 Project 后续发生变化，都不能改变已有 Project Version 的内容。

---

### 3.2.7 Project Branch

```text
对象名称：
Project Branch

定义：
Project 内指向某个 Project Version 的可变开发引用。

归属：
属于一个 Project。

可变性：
分支指向的最新 Project Version 可以变化。

约束：
分支不能指向其他 Project 的 Project Version。
```

分支是开发组织方式，不是独立 Project。

Fork 创建的是新 Project，不是源 Project 中的新分支。

---

### 3.2.8 Run Configuration

```text
对象名称：
Run Configuration

定义：
Project 下可命名、可编辑、可复用的运行方案。

归属：
属于一个 Project。

主要内容：
├── 工作目录
├── 执行命令
├── Environment Selection
├── Input Binding
├── Compute Request 或 Compute Plan
├── Artifact Collection Rule
└── Credential Reference

可变性：
可以修改、复制和删除。

与 Run 的关系：
创建 Run 时，运行方案被解析并复制进 Run Snapshot。
后续修改运行方案不会影响历史 Run。
```

Run Configuration 是“期望如何运行”的可变配置。

Run Snapshot 是“这次实际如何运行”的不可变记录。

---

### 3.2.9 Environment 与 Environment Version

```text
对象名称：
Environment

定义：
可被多个 Project 引用的独立运行基础。

所有者：
├── Platform
└── Workspace

主要关系：
├── 包含多个 Environment Version
├── 可以授权其他 Workspace 使用
└── 可以被设置为 Workspace 默认环境

可变性：
名称、说明、共享范围等元数据可以修改。
```

```text
对象名称：
Environment Version

定义：
Environment 已发布的确定版本。

可变性：
发布后不可修改。

主要用途：
├── 被 Project 显式选择
├── 作为 Workspace 默认环境的目标版本
└── 被 Run Snapshot 固定
```

Project 可以配置：

```text
继承 Workspace 默认环境
或
显式选择 Environment Version
```

创建 Run 时必须解析为确定的 Environment Version。

---

### 3.2.10 Shared Resource 与 Shared Resource Version

```text
对象名称：
Shared Resource

定义：
独立于 Project 存在、可版本化、可授权复用的内容资源。

所有者：
├── Platform
└── Workspace

主要关系：
├── 包含多个 Shared Resource Version
├── 可以向其他 Workspace 发放 Access Grant
└── 可以被 Project 通过 Input Binding 引用

可变性：
名称、说明、推荐版本和授权配置可以修改。
```

```text
对象名称：
Shared Resource Version

定义：
Shared Resource 已发布的确定内容版本。

可变性：
发布后不可修改。

主要用途：
├── 绑定到 Project
├── 作为 Run 输入
├── 被 Run Snapshot 固定
└── 作为其他版本的派生来源
```

Shared Resource Version 默认只读提供给 Run。

---

### 3.2.11 Artifact

```text
对象名称：
Artifact

定义：
某次 Run 产生并保存的不可变结果。

归属：
属于产生它的 Run；
因此归属于该 Run 所在 Project 的 Workspace。

主要关系：
├── 来源 Run
├── 内容身份或摘要
├── Artifact 文件或目录
├── 可以作为后续 Run 的输入
├── 可以复制到 Project
└── 可以发布为 Shared Resource Version

可变性：
内容不可修改。
名称、说明等展示元数据可以在允许范围内修改。
```

从仍被保留的 Run 工作目录补充收集输出时，应创建新的 Artifact，而不是修改已有 Artifact。

---

### 3.2.12 Input Binding

```text
对象名称：
Input Binding

定义：
将确定输入对象绑定到运行访问位置的关系。

来源类型：
├── Shared Resource Version
└── Artifact

主要内容：
├── Source Type
├── Source ID
├── Access Path
├── Read-only
└── 可选的内容身份或摘要

存在位置：
├── Run Configuration 中的可编辑输入配置
└── Run Snapshot 中的不可变输入记录
```

Input Binding 本身不复制输入内容。

它表示：

```text
使用哪个确定对象
以及
在运行中通过什么位置访问
```

---

### 3.2.13 Workspace Credential

```text
对象名称：
Workspace Credential

定义：
由 Workspace 管理、供 Project 或 Run 使用的秘密信息。

典型内容：
├── Git Token
├── SSH Key
├── 对象存储凭据
├── API Key
└── 外部服务凭据

归属：
属于一个 Workspace。

使用方式：
Project 或 Run Configuration 只能保存凭据引用，
不能保存凭据明文。

可变性：
秘密值可以轮换；
凭据可以停用或撤销。
```

Credential 不随 Project Fork、模板使用或跨 Workspace 复制传播。

---

### 3.2.14 Resource Entitlement

```text
对象名称：
Resource Entitlement

定义：
某个 Workspace 被允许使用的计算、存储和调度资源范围。

持有者：
一个 Workspace。

可能的提供者：
├── Platform
└── 其他明确提供额度的 Workspace

主要内容：
├── 可使用的 Cluster
├── 可使用的 Compute Plan
├── CPU、内存、GPU 和节点上限
├── 并发和累计额度
├── 可使用的 Account、Partition 和 QoS 范围
├── 生效时间
└── 到期时间
```

Resource Entitlement 只代表使用资格，不代表数据访问权限。

---

### 3.2.15 Entitlement Request

```text
对象名称：
Entitlement Request

定义：
Workspace 请求新增、提升或续期资源权益的申请。

申请主体：
Workspace。

提交人：
具有申请权限的 Workspace 成员。

主要内容：
├── 目标资源权益
├── 用途
├── 预计期限
├── 可选关联 Project 或场景
└── 审批结果

生命周期：
Draft
→ Submitted
→ Reviewing
→ Approved / Partially Approved / Rejected / Withdrawn
```

获批后应创建或调整 Resource Entitlement，而不是直接修改某个 Run。

---

### 3.2.16 Compute Plan、Compute Request 与 Scheduler Mapping

```text
对象名称：
Compute Plan

定义：
向用户展示的命名算力组合。

示例：
├── CPU 快速测试
├── CPU 标准
├── GPU 标准
└── 大显存训练
```

```text
对象名称：
Compute Request

定义：
某个 Run Configuration 或 Run 对资源的逻辑请求。

主要内容：
├── 节点数
├── CPU
├── 内存
├── GPU
├── 最长运行时间
└── 可选调度偏好
```

```text
对象名称：
Scheduler Mapping

定义：
将 Compute Request 和 Resource Entitlement 解析为底层调度参数的规则。

输出：
├── Cluster
├── Account
├── Partition
├── QoS
└── 其他调度参数
```

Compute Plan 可以生成 Compute Request。

Compute Request 必须经过权益和平台规则校验后，才能解析为最终调度配置。

---

### 3.2.17 Run

```text
对象名称：
Run

定义：
Project 的一次独立计算执行记录。

归属：
属于一个 Project；
因此归属于该 Project 的 Workspace。

主要关系：
├── Run Snapshot
├── Scheduler Job
├── Log
├── Artifact
├── Metric
└── 来源 Run

可变性：
Run Snapshot 不可修改；
执行状态、调度信息和时间信息可以更新。
```

每次重新运行都创建新的 Run。

历史 Run 不会被重置、覆盖或重新使用为同一条执行记录。

---

### 3.2.18 Run Snapshot

```text
对象名称：
Run Snapshot

定义：
Run 创建时固定的完整执行事实。

主要内容：
├── 来源 Project
├── Project Version
├── 来源 Run Configuration
├── 工作目录
├── 最终执行命令
├── Environment Version
├── Input Binding
├── Credential Reference
├── Compute Request
├── 最终调度配置
├── Artifact Collection Rule
├── 创建人
└── 创建时间

可变性：
创建后不可修改。
```

Run Snapshot 不保存凭据明文，只保存受控引用和执行时需要的最小标识。

---

### 3.2.19 Template 与 Template Revision

```text
对象名称：
Template

定义：
面向发现和复用的目录入口。

主要内容：
├── 名称
├── 简介
├── 分类和标签
├── 可见范围
└── 推荐 Template Revision

可变性：
展示信息和推荐修订可以修改。
```

```text
对象名称：
Template Revision

定义：
模板在一次发布时固定引用的 Project Version。

可变性：
发布后不可修改。

使用结果：
从 Template Revision 创建新的 Project。
```

发布新来源版本时，应创建新的 Template Revision，而不是修改已有修订指向的 Project Version。

---

### 3.2.20 Fork Relation

```text
对象名称：
Fork Relation

定义：
记录派生 Project 与来源 Project Version 的关系。

主要内容：
├── Source Project
├── Source Project Version
├── Target Project
├── 操作者
└── 创建时间

可变性：
创建后不可修改。
```

Fork Relation 只记录来源，不让两个 Project 形成持续同步关系。

---

### 3.2.21 Profile、Profile Version 与 Profile Instance

```text
对象名称：
Profile

定义：
将平台基础能力组合为垂直场景的产品定义。

对象名称：
Profile Version

定义：
Profile 已发布的确定版本。

对象名称：
Profile Instance

定义：
某个 Workspace 启用确定 Profile Version 后形成的场景实例。
```

Profile Instance 归属于一个 Workspace。

它可以增加场景对象和场景规则，但不能绕过 Workspace 基础权限。

---

### 3.2.22 Assignment

```text
对象名称：
Assignment

定义：
Course Profile 中由教师发布的任务。

归属：
属于启用了 Course Profile 的 Collaborative Workspace。

主要关系：
├── 起始 Project Version
├── 推荐 Environment
├── 推荐 Shared Resource
├── 推荐 Compute Plan
├── 发布时间和截止时间
└── Submission Requirement
```

Assignment 引用确定的 Project Version 作为起始内容。

Assignment 发布后，修改起始内容应产生新的 Assignment 修订或明确的新版本，而不能静默改变学生已看到的内容。

---

### 3.2.23 Submission

```text
对象名称：
Submission

定义：
学生显式提交到 Course Workspace 的不可变内容副本。

来源：
学生 Personal Workspace 中的确定 Project Version。

归属：
归属于 Course Workspace。

主要关系：
├── Assignment
├── 提交人
├── 来源 Project 和 Project Version 标识
├── 不可变提交内容
├── 提交时间
└── 可选 Artifact 或结果摘要

可变性：
提交内容不可修改。
```

新的提交应产生新的 Submission。

后一次提交可以将前一次标记为已被替代，但不能修改前一次 Submission 的内容。

---

## 3.3 核心对象关系

```text
User
├── owns ────────────────> Personal Workspace
└── Membership ──────────> Collaborative Workspace

Workspace
├── owns ────────────────> Project
├── holds ───────────────> Resource Entitlement
├── owns ────────────────> Workspace Credential
├── may own ─────────────> Environment
├── may own ─────────────> Shared Resource
└── enables ─────────────> Profile Instance

Project
├── has ─────────────────> Project Working Tree
├── has ─────────────────> Project Branch
├── saves ───────────────> Project Version
├── has ─────────────────> Run Configuration
├── creates ─────────────> Run
└── may derive from ─────> Project Version

Run Configuration
├── selects ─────────────> Environment Version
├── contains ────────────> Input Binding
├── contains ────────────> Compute Request
├── references ──────────> Workspace Credential
└── defines ─────────────> Artifact Collection Rule

Input Binding
├── references ──────────> Shared Resource Version
└── references ──────────> Artifact

Run
├── fixes ───────────────> Run Snapshot
├── maps to ─────────────> Scheduler Job
├── produces ────────────> Log
├── produces ────────────> Artifact
└── reports ─────────────> Metric

Template
└── contains ────────────> Template Revision
                              └── references Project Version

Course Profile Instance
├── owns ────────────────> Assignment
└── owns ────────────────> Submission

Assignment
└── references ──────────> Starter Project Version

Submission
└── copies from ─────────> Student Project Version
```

---

## 3.4 全局产品不变量

以下规则适用于所有模块。后续领域规则不得与这些不变量冲突。

### GR-001 Workspace 是基础归属边界

```text
1. Project 必须且只能属于一个 Workspace。
2. Run 必须属于一个 Project。
3. Log 和 Artifact 必须属于产生它们的 Run。
4. Run、Log 和 Artifact 的归属 Workspace 由 Project 决定。
5. Membership 只在对应 Workspace 内生效。
```

---

### GR-002 对象归属与资源记账相互独立

```text
对象归属于哪个 Workspace
≠
本次资源消耗由哪个 Workspace 承担
```

例如，学生 Personal Workspace 中的 Run 可以消耗 Course Workspace 提供的计算额度。

这不会改变：

```text
Project、Run、Log 和 Artifact 仍属于学生 Personal Workspace。
```

Course Workspace 可以查看其提供额度的消费记录，但不能因此读取 Run 内容。

---

### GR-003 可变对象与不可变版本必须分离

可变对象包括：

```text
Workspace
Project
Project Working Tree
Run Configuration
Environment
Shared Resource
Template
Profile Instance
```

不可变对象包括：

```text
Project Version
Environment Version
Shared Resource Version
Template Revision
Run Snapshot
Artifact
Submission
```

修改不可变内容时，必须创建新版本或新对象。

---

### GR-004 引用不会复制内容

引用表示继续使用同一个来源对象。

```text
引用对象
→ 受来源对象当前授权和可用状态约束
```

引用至少应记录：

```text
来源对象标识
确定版本
访问位置
引用类型
```

---

### GR-005 复制产生独立内容

复制表示在目标归属范围内创建独立内容。

```text
复制完成后：
├── 源内容后续变化不影响副本
└── 副本后续变化不影响源内容
```

Submission 必须采用复制语义，而不是仅保存指向学生 Personal Workspace 的访问引用。

---

### GR-006 Fork 不传播权限和权益

Fork 可以复制：

```text
Project 文件
运行方案
环境选择信息
Input Binding 信息
算力请求
Artifact 收集规则
```

Fork 不复制：

```text
源 Workspace 成员权限
Environment Grant
Shared Resource Grant
Resource Entitlement
Workspace Credential
Run 历史
Log
Artifact
```

复制的引用必须在目标 Workspace 中重新校验。

---

### GR-007 所有外部引用在使用时重新校验

以下操作必须检查当前权限和可用性：

```text
创建 Run
重新运行历史 Run
从模板创建 Project
Fork Project
切换 Environment Version
使用 Shared Resource Version
将 Artifact 作为输入
```

历史上曾经成功使用，不代表当前仍然可以使用。

---

### GR-008 历史事实与当前访问权分离

历史记录可以继续显示：

```text
曾经使用的环境标识
曾经使用的资源版本标识
曾经使用的 Artifact 标识
曾经解析出的 Account、Partition 和 QoS
```

但历史记录不自动授予当前内容访问权。

---

### GR-009 Run Snapshot 创建后不可修改

Run 提交前可以修改 Run Draft。

创建 Run Snapshot 后，不允许修改：

```text
代码版本
执行命令
工作目录
环境版本
输入来源
算力请求
最终调度配置
Artifact 收集规则
```

需要改变任何内容时，必须创建新 Run。

---

### GR-010 Artifact 可以直接作为后续输入

Artifact 不必先发布为 Shared Resource。

```text
Artifact
├── 可以直接作为后续 Run 输入
├── 可以复制到 Project
└── 可以发布为 Shared Resource Version
```

是否发布为 Shared Resource，取决于是否需要独立管理、稳定版本、长期复用或扩大共享范围，而不是取决于文件大小。

---

### GR-011 输入默认只读

Shared Resource Version 和 Artifact 作为 Run 输入时，默认以只读方式提供。

Run 不得原地修改输入对象。

程序需要修改输入时，应先：

```text
复制到 Run 工作目录
或
复制到 Project
```

---

### GR-012 Credential 不得通过普通对象传播

```text
Project Fork
模板创建
Project 复制
运行方案复制
跨 Workspace 迁移
```

均不得复制凭据秘密值或原授权。

目标 Workspace 必须重新绑定自己有权使用的 Credential。

---

### GR-013 无发现权限时对象视为不存在

对于没有发现权限的 Environment、Shared Resource、Project、Artifact 等对象：

```text
搜索结果中不出现
列表中不出现
直接访问时不泄露对象信息
```

平台不得通过不同错误信息泄露隐藏对象是否存在。

---

### GR-014 平台管理员权限不等于内容访问权

平台管理员默认可以查看完成运维所需的元数据，例如：

```text
对象标识
归属关系
资源请求
调度状态
时间信息
错误类型
容量和记账数据
```

平台管理员默认不能任意查看：

```text
Project 代码
Run 执行命令
完整日志内容
Artifact 内容
Credential 内容
```

确有支持需要时，应通过受控支持访问流程，并记录原因、范围、期限和审计记录。

---

### GR-015 Slurm 是实际调度状态的事实来源

107 Workspace 负责：

```text
产品对象
权限校验
Run Snapshot
调度请求解析
用户可见状态映射
```

Slurm 负责：

```text
排队
资源分配
节点选择
任务执行
底层任务状态
```

107 不重新实现调度算法。

当平台记录与 Slurm 状态不一致时，应保留异常状态并执行同步或人工处置，不能直接伪造成功状态。

---

### GR-016 删除不能重写历史事实

内容清理可以删除实际文件，但不得篡改已经形成的历史关系。

例如 Artifact 内容被清理后，历史 Run 仍应保留：

```text
Artifact 标识
名称
内容摘要
原始大小
产生时间
来源 Run
清理状态
```

被运行方案持续引用的对象，在清理前必须进行影响检查。

---

这一部分确定后，下一部分应继续写：

```text
3.5 限界上下文与领域职责
3.6 核心工作流
3.7 对象生命周期与状态机
3.8 权限与可见性规则
```

其中优先顺序应为：

```text
限界上下文
→ Project 创建与运行工作流
→ Fork 工作流
→ Artifact 输入工作流
→ 权益申请工作流
→ Assignment 与 Submission 工作流
```
