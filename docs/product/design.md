# 产品设计

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
| 模板修订 | Template Revision | Template 在某次发布时形成的不可变模板内容版本，用于创建新的 Project |

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
→ Workspace 有权使用哪些算力方案

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
1. Workspace 只能使用其 Resource Entitlement 允许的 Compute Plan。

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
├── Input Binding
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
  如 Membership、Fork Relation 和 Workspace Asset Grant 关系。
```

#### 3.2.1 对象归属关系

主要对象归属如下：

```text
Platform
├── Compute Plan
├── Environment *
│   └── Environment Version
└── Shared Resource *
    └── Shared Resource Version

Workspace
├── Project
│   ├── Project Working State
│   ├── Project Version
│   ├── Project Branch
│   ├── Run Configuration
│   └── Run
│       ├── Run Snapshot
│       ├── Log
│       ├── Artifact
│       ├── Metric
│       └── Resource Usage Record
│
├── Template
│   └── Template Revision
├── Profile
│   └── Profile Version
├── Environment *
│   └── Environment Version
├── Shared Resource *
│   └── Shared Resource Version
├── Variable
├── Secret
├── Resource Entitlement
├── Entitlement Request
└── Profile Instance
```

其中：

```text
* Environment 和 Shared Resource
  可以由 Platform 持有，也可以由某个 Workspace 持有。

Project、Template、Profile
→ 属于 Workspace。

Project Working State、Project Version、
Project Branch、Run Configuration
→ 属于对应 Project。

Run
→ 属于对应 Project。

Run Snapshot、Log、Artifact、Metric、
Resource Usage Record
→ 属于对应 Run。

Template Revision、Profile Version、
Environment Version、Shared Resource Version
→ 属于各自的上级对象。

Variable、Secret、Resource Entitlement、
Entitlement Request、Profile Instance
→ 属于 Workspace。

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
├── Environment
├── Compute Plan
├── Input Binding
│   ├── Shared Resource Version
│   └── Artifact
└── Environment Variable
    ├── Variable
    └── Secret

Run
└── Source Run Configuration（可选）

Run Snapshot
├── Project Version
├── Environment Version
├── Compute Plan
└── Input Binding
    ├── Shared Resource Version
    └── Artifact

Resource Entitlement
└── Compute Plan

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
→ 表示 Workspace 获得某个 Compute Plan 的使用资格。

Profile Instance
→ 引用确定的 Profile Version。
```

---

#### 3.2.3 关系总览

图例：

```text
├──   归属关系
──▶   引用关系
··▶   可选引用关系
*     可以由 Platform 或 Workspace 持有
```

```text
User
   ╲
    Membership
   ╱
Workspace
│
├── Project
│   ├── Project Working State
│   ├── Project Version ◀──── Project Branch
│   │
│   ├── Run Configuration
│   │   ├──▶ Environment
│   │   ├──▶ Compute Plan
│   │   ├── Input Binding ──▶ Shared Resource Version / Artifact
│   │   └── Environment Variable ──▶ Variable / Secret
│   │
│   └── Run
│       ├··▶ Source Run Configuration
│       │
│       ├── Run Snapshot
│       │   ├──▶ Project Version
│       │   ├──▶ Environment Version
│       │   ├──▶ Compute Plan
│       │   └── Input Binding ──▶ Shared Resource Version / Artifact
│       │
│       ├── Log
│       ├── Artifact
│       ├── Metric
│       └── Resource Usage Record
│
├── Template
│   └── Template Revision
│
├── Profile
│   └── Profile Version
│
├── Profile Instance ──────────────▶ Profile Version
│
├── Environment *
│   └── Environment Version
│
├── Shared Resource *
│   └── Shared Resource Version
│
├── Variable
├── Secret
│
├── Resource Entitlement ─────────▶ Compute Plan
│
└── Entitlement Request


Platform
├── Compute Plan
├── Environment *
│   └── Environment Version
└── Shared Resource *
    └── Shared Resource Version


Source Project Version
        ╲
     Fork Relation
        ╱
Target Project


Workspace
        ╲
 Workspace Asset Grant
        ╱
Environment / Shared Resource
```

这里有几个关键语义：

```text
Membership
→ 连接 User 与 Workspace，表示 User 在 Workspace 的身份。
  User 是身份主体，Workspace 是主要的成员、权限和业务对象治理边界。
  User 通过 Membership 与 Workspace 建立成员关系。

Project Version
→ 提供 Run 自身的项目内容。

Input Binding
→ 提供额外输入内容，
  来源为 Shared Resource Version 或 Artifact。

Run Configuration
→ 保存可编辑、可复用的引用和配置。

Run Snapshot
→ 固定本次执行实际使用的确定版本、输入和配置。

Profile Instance
→ 属于启用它的 Workspace，
  引用确定的 Profile Version。

Resource Entitlement
→ 使 Workspace 获得 Compute Plan 的使用资格。

Workspace Asset Grant
→ 使 Workspace 获得其他 Workspace 或 Platform
  所持 Environment / Shared Resource 的使用资格。

Environment、Shared Resource
→ 可以由 Platform 或 Workspace 持有。

Fork Relation
→ 记录新 Project 从哪个 Project Version 派生。
```

本图用于概括核心领域对象的主要归属和引用关系，不表示数据库表结构、外键关系或具体实现依赖。

---

### 3.3 核心产品规则

#### 3.3.0 规则标识与演进规范

核心产品规则使用 `GR-xxx` 作为稳定标识，其中 `GR` 表示 Global Rule。

规则编号按类别划分：

```text
GR-1xx  Workspace 与权限边界
GR-2xx  版本、快照与历史一致性
GR-3xx  Run 与执行
GR-4xx  资源使用与跨 Workspace
GR-5xx  派生、复用与扩展

GR-6xx ~ GR-9xx
→ 保留给未来新增规则类别
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

#### 3.3.1 Workspace 与权限边界

##### **GR-101 — Workspace 对象归属**

Project、Template、Profile、Variable、Secret、Resource Entitlement、Entitlement Request 和 Profile Instance 必须且只能属于一个 Workspace。

##### **GR-102 — Membership 操作边界**

User 必须通过有效 Membership，才能以 Workspace 成员身份操作该 Workspace 内的对象。

##### **GR-103 — Membership Role 权限**

User 在 Workspace 中可执行的操作必须受其 Membership Role 约束。

##### **GR-104 — Collaborative Workspace 所有权**

Collaborative Workspace 必须始终具有唯一的有效 Owner；Owner 转移完成前不得移除或退出原 Owner。

##### **GR-105 — 权限与资源资格分离**

当 User 在 Workspace 中执行涉及外部资产或 Compute Plan 的操作时，平台必须分别校验：

- User 是否具有有效 Membership，且其 Membership Role 是否允许执行该操作；
- Workspace 使用外部 Environment 或 Shared Resource 时，是否具有对应的有效 Workspace Asset Grant；
- Workspace 使用 Compute Plan 时，是否具有对应的有效 Resource Entitlement。

任一项校验通过，不得视为其他校验同时通过。

##### **GR-106 — 平台管理权限与 Workspace 数据权限分离**

Platform 级管理权限只能授予对应的平台管理操作，不得仅因具有 Platform 管理角色而自动获得 Workspace 私有内容的读取权限或 Secret 明文访问权限。

---

#### 3.3.2 版本、快照与历史一致性

##### **GR-201 — 版本内容不可变**

Project Version、Environment Version、Shared Resource Version、Template Revision 和 Profile Version 创建后，其已版本化内容不得原地修改；内容发生变化时必须形成新的 Version 或 Revision。

##### **GR-202 — Run Snapshot 不可变**

Run Snapshot 创建后不得修改；Run 创建之后发生的配置变化不得回写已有 Run Snapshot。

##### **GR-203 — Artifact 内容不可变**

Artifact 创建后，其内容不得原地修改；需要保存不同内容时必须形成新的 Artifact。

##### **GR-204 — 历史对象不受后续修改影响**

对 Project Working State、Run Configuration、Environment、Shared Resource、Template 或 Profile 的后续修改，只能影响之后创建的版本、配置或 Run，不得改变已经形成的 Version、Revision、Run Snapshot 或 Artifact。

##### **GR-205 — 确定引用不得漂移**

Run Snapshot 中需要固定的对象引用必须指向确定的 Version 或 Artifact；引用一经形成，不得因 `current`、`latest`、默认版本或上级对象更新而自动改变目标。

Secret 等明确采用运行时解析机制的引用不受本规则约束。

##### **GR-206 — 不可变性与生命周期独立**

Project Version、Run Snapshot、Artifact 等不可变对象在其存在期间不得原地修改；不可变性不表示永久保留。

当其所属的 Project、Run 等上级对象被删除时，可以随所属生命周期一并删除；已经通过发布、派生等操作形成的独立对象不受源对象删除影响。

---

#### 3.3.3 Run 与执行规则

##### **GR-301 — Run 归属**

每个 Run 必须且只能属于一个 Project。

##### **GR-302 — Run Snapshot 生成**

创建 Run 时，平台必须生成独立的 Run Snapshot，并在其中固定本次执行使用的 Project Version、执行配置及相关资源版本。

若 Run 基于 Run Configuration 创建，其内容必须在创建 Run 时解析并固化到 Run Snapshot。

##### **GR-303 — Run 执行配置依据**

Run 的执行必须以其 Run Snapshot 为唯一配置依据；创建 Run 后发生的 Project、Run Configuration 或相关资源变化不得改变本次执行配置。

##### **GR-304 — Secret 执行规则**

Run Snapshot 不得保存 Secret 明文；需要使用 Secret 时，只能保存其引用，并由平台在执行时按当前有效授权安全提供对应值。

##### **GR-305 — 执行结果与执行快照分离**

Run Snapshot 只能记录执行开始前已确定的输入和配置；Log、Artifact、Metric 和 Resource Usage Record 等执行过程中或执行完成后产生的信息不得作为 Run Snapshot 的组成部分。

##### **GR-306 — Run 执行唯一性**

每个 Run 只能表示一次逻辑执行。用户对已有 Run 发起重新执行时，平台必须创建新的 Run 和新的 Run Snapshot，不得复用原 Run 表示新的执行。

---

#### 3.3.4 资源使用与跨 Workspace 规则

##### **GR-401 — Environment 与 Shared Resource 使用资格**

Workspace 可以使用自身持有的 Environment 和 Shared Resource；使用 Platform 或其他 Workspace 持有的 Environment 或 Shared Resource 时，必须具有对应的有效 Workspace Asset Grant。

##### **GR-402 — 资源授权与版本固定分离**

Workspace Asset Grant 作用于顶层 Environment 或 Shared Resource；创建 Run 时，必须在 Run Snapshot 中固定本次实际使用的 Environment Version 或 Shared Resource Version。

##### **GR-403 — Input Binding 内容确定性**

Input Binding 必须引用确定的输入内容，其来源只能是 Shared Resource Version 或 Artifact。

##### **GR-404 — 输入源只读**

通过 Input Binding 提供的输入不得被 Run 原地修改；运行过程中需要产生或修改的内容必须写入本次 Run 的可写空间，并按需要形成 Artifact。

##### **GR-405 — Artifact Workspace 边界**

Artifact 可以直接作为同一 Workspace 中后续 Run 的 Input Binding 来源；Artifact 不得直接跨 Workspace 作为输入使用。

需要跨 Workspace 使用 Artifact 内容时，必须先将其发布为 Shared Resource，并按照 Shared Resource 的授权规则使用。

##### **GR-406 — Compute Plan 使用资格**

Workspace 只能使用其有效 Resource Entitlement 所允许的 Compute Plan。

##### **GR-407 — Secret 跨 Workspace 隔离**

Secret 的值和访问权限不得因 Fork、Template 或其他跨 Workspace 的派生、复用行为而自动复制或继承到目标 Workspace。

配置中对 Secret 的引用表达式可以被复制，但必须在目标 Workspace 中重新解析并满足其自身的 Secret 和权限条件。

##### **GR-408 — Ownership 变更后的授权失效**

Environment 或 Shared Resource 的 Ownership 发生变化后，基于原 Owner 建立的 Workspace Asset Grant 不再有效；后续使用资格必须由新的 Owner 重新授权。

---

#### 3.3.5 派生、复用与扩展规则

##### **GR-501 — Fork 来源与追踪**

Fork 必须从确定的 Project Version 创建新的 Project，并记录 Source Project Version 与目标 Project 之间的 Fork Relation。

##### **GR-502 — Fork 后独立**

Fork 完成后，目标 Project 具有独立生命周期；源 Project 与目标 Project 的后续修改或删除不得相互影响。

##### **GR-503 — Fork 权限与历史隔离**

Fork 可以复制 Project 内容、Run Configuration 以及可复用的资源引用，但不得复制或继承源 Workspace 的 Membership、Resource Entitlement、Secret 值及其访问权限，也不得复制源 Project 的 Run 历史和执行结果。

被复制的资源引用不得使目标 Workspace 自动继承源 Workspace 的使用资格，实际使用时必须按照目标 Workspace 的权限与资源资格重新校验。

##### **GR-504 — Template 创建独立性**

通过 Template Revision 创建 Project 后，目标 Project 必须独立存在，不得依赖 Template Revision 的后续状态或更新。

Template 发布新的 Revision 不得改变已经创建的 Project。

##### **GR-505 — Profile Instance 版本固定**

Profile Instance 必须基于确定的 Profile Version 创建，并固化其生效定义；源 Profile 或 Profile Version 的后续变化和删除不得改变已有 Profile Instance。

##### **GR-506 — Profile 显式升级**

已有 Profile Instance 切换到其他 Profile Version 时，必须通过明确的升级操作完成，不得因 Profile 默认版本或最新版本变化而静默升级。

##### **GR-507 — Profile 扩展边界**

Profile 可以组合平台基础能力、默认配置和场景工作流，但其扩展不得改变或绕过 Workspace 的归属与权限边界、版本不可变规则以及 Run Snapshot 的执行语义。

---

### 3.4 核心领域操作

#### 3.4.1 Workspace 生命周期与治理操作

##### 开通 Personal Workspace

当 User 符合 Personal Workspace 使用资格且当前不存在有效 Personal Workspace 时，平台为其开通一个 Personal Workspace。

同一 User 同一时刻最多存在一个有效 Personal Workspace。Personal Workspace 在其有效期间仅供对应 User 使用，不支持其他 User 加入或 Owner 转移。

Personal Workspace 使用资格独立于 User 的平台访问资格和 Collaborative Workspace Membership。

##### 创建 Collaborative Workspace

具有创建权限的 User 可以创建 Collaborative Workspace。

创建时必须建立创建者的 Membership，并确定唯一 Owner。

Collaborative Workspace 具有独立生命周期，不依赖创建者的 Personal Workspace。

##### 删除 Workspace

Personal Workspace 在对应 User 失去使用资格后结束正常使用，并可以按照平台规则删除；Collaborative Workspace 可以由具有相应权限的主体显式删除。

Workspace 删除时，仍归属于该 Workspace 的对象随其生命周期结束；已经转移，或已经通过派生、实例化等操作形成独立生命周期的对象不受影响。

Workspace 删除不得删除 User 身份，也不得影响 User 在其他 Workspace 中独立存在的 Membership。

##### 管理 Membership

Collaborative Workspace 支持建立 Membership、变更 Role、退出和移除成员。

Membership 的变化只影响对应 User 在该 Workspace 中的成员身份和操作权限，不改变 Workspace 已有对象、资源资格及其他 Membership。

Membership 管理不得破坏 Collaborative Workspace 唯一有效 Owner 的约束；Owner 变更必须通过 Owner 转移操作完成。

##### 转移 Collaborative Workspace Owner

Collaborative Workspace 可以通过显式操作将 Owner 转移给另一有效成员。

转移完成后必须保持唯一有效 Owner；当前 Owner 在完成转移前不得退出或被移除。

##### 管理 Workspace Variable 与 Secret

Workspace 可以创建、修改和删除 Variable，以及创建、更新、轮换和删除 Secret。

Variable 在创建 Run Snapshot 时解析并固定，后续变化不得影响已有 Snapshot 中已经固定的值。

Secret 在 Run Snapshot 中仅保留引用，不保存明文；Secret 的实际取值按照执行时的有效引用与权限解析，Secret 变化不得回写 Run Snapshot。

#### 3.4.2 Project 生命周期、版本与运行配置操作

##### 创建 Project

Workspace 可以创建新的 Project，并产生其初始 Project Working State。

Project 支持以下初始化来源：

- Blank：创建空白 Project；
- From Project Version：基于确定的 Project Version 创建独立 Project，并建立 Fork Relation；
- From Template Revision：基于确定的 Template Revision 创建独立 Project。

基于已有对象创建 Project 时，可以复制允许复用的内容、配置和资源引用，但不得继承源 Workspace 的 Membership、Workspace Asset Grant、Resource Entitlement、Secret 值，以及源对象的运行历史和结果；涉及外部资源的引用必须按照目标 Workspace 的权限重新校验。

创建完成后，Project 具有独立生命周期，不持续依赖其初始化来源。

##### 编辑 Project Working State

Project Working State 表示 Project 当前可编辑的工作内容。

用户可以在权限允许的范围内修改 Working State。对 Working State 的修改不得改变已经创建的 Project Version，也不得影响已有 Run Snapshot。

##### 创建 Project Version

可以基于 Project 当前 Working State 创建新的 Project Version。

Project Version 创建后内容不可变，用于固定某一确定的 Project 状态，并可以作为创建 Run 或新 Project 的确定来源。

后续对 Working State 的修改不得改变已有 Project Version。

##### 管理 Project Branch

Project 可以创建、移动和删除 Project Branch。

Project Branch 是指向本 Project 某一确定 Project Version 的可变引用；移动 Branch 只改变其指向，不修改任何 Project Version。

##### 管理 Run Configuration

Project 可以创建、修改和删除 Run Configuration，用于保存可复用的运行计划。

Run Configuration 可以描述 Working Directory、Command、Environment、Input Bindings、Environment Variables、Compute Plan、Compute Request 和 Artifact Collection Rules 等运行参数及引用。

Run Configuration 本身可以继续修改；创建 Run 时，所采用的配置按照 Run 创建规则解析并固定到 Run Snapshot。后续修改 Run Configuration 不得改变已有 Run Snapshot。

##### 删除 Project

具有相应权限的主体可以删除 Project。

Project 删除时，其 Working State、Project Version、Project Branch、Run Configuration，以及归属于该 Project 的 Run 和 Run 从属对象随其生命周期结束。

已经形成独立生命周期的对象不因源 Project 删除而删除，例如基于其 Project Version 创建的其他 Project，或由其运行结果发布形成的独立资源。

#### 3.4.3 Run 生命周期与执行操作

##### 创建 Run

可以在 Project 下创建新的 Run。创建时必须确定本次执行使用的 Project Version，并将运行配置解析并固定到独立的 Run Snapshot；若配置来源于 Run Configuration，则以创建 Run 时该 Run Configuration 的当前内容为准。

创建 Run 时必须校验当前操作权限，以及本次执行所需的资源访问资格和算力资格，包括适用时的 Workspace Asset Grant 和 Resource Entitlement。

Run Snapshot 固定本次执行采用的 Project Version、解析后的运行配置以及确定的输入和资源引用。Secret 仅固定引用，不保存明文。

Run 创建后，Project、Run Configuration 及相关可变配置的后续变化不得改变已有 Run Snapshot。

##### 提交与执行 Run

Run 按照其 Run Snapshot 提交并执行。

Run Snapshot 是本次 Run 执行配置的唯一依据；提交和执行时不得重新读取 Project Working State、Run Configuration，或将已经固定的版本引用重新解析为 current、latest 等可变目标。

执行过程中可以按照 Snapshot 中保存的 Secret 引用，在当前有效权限下安全取得实际 Secret 值。

一个 Run 表示一次逻辑执行。

##### 更新 Run 执行状态与执行信息

Run 在执行过程中可以更新 Status、Submitted At、Started At、Finished At、Exit 信息和 Scheduler Job Reference 等执行信息。

这些信息描述 Run 的实际执行过程，不属于 Run Snapshot，也不得改变 Snapshot 中已经固定的执行配置。

##### 记录执行输出与结果

Run 执行过程中及执行结束后，可以产生 Log、Metric 和 Resource Usage Record，并按照 Artifact Collection Rules 收集 Artifact。

这些对象记录本次实际执行产生的日志、结果和资源使用情况，不属于 Run Snapshot。

Artifact 内容形成后不可变，并可以按照相应资源规则作为后续 Run 的输入或发布为 Shared Resource。

##### 取消 Run

具有相应权限的主体可以取消尚未结束且允许取消的 Run。

取消结束本次逻辑执行，但不删除 Run、Run Snapshot 以及此前已经产生的执行记录和结果。

##### 重新执行 Run

用户重新执行已有 Run 时，必须创建新的 Run，并生成新的 Run Snapshot。

新的 Run 可以以原 Run 的执行配置作为创建来源，但必须按照新 Run 创建时的权限和资源资格重新校验。原 Run 中已经确定的版本或输入引用可以继续作为新 Run 的确定引用，不得因重新执行而自动漂移至其他版本。

#### 3.4.4 资源、授权与算力资格操作

##### 管理 Environment 与 Environment Version

Platform 或 Workspace 可以创建、维护和删除 Environment，并创建不可变的 Environment Version。

Run 使用 Environment 时必须确定具体 Environment Version；Environment 的后续变化不得影响已有 Version 或 Run Snapshot。

##### 管理 Shared Resource 与 Shared Resource Version

Platform 或 Workspace 可以创建、维护和删除 Shared Resource，并创建不可变的 Shared Resource Version。

Artifact 可以发布形成具有独立生命周期的 Shared Resource。Run 使用 Shared Resource 时必须确定具体 Shared Resource Version。

##### 转移 Workspace-owned 可复用对象

支持转移的 Workspace-owned 对象可以显式转移至另一 Workspace。

转移改变对象的 Owner 和生命周期边界，但不改变已有版本内容。源 Workspace 的 Membership、Resource Entitlement 和 Secret 不随对象转移。

对于支持 Workspace Asset Grant 的对象，Ownership 发生变化后，既有 Grant 不再有效；后续使用资格必须由新的 Owner 重新授权。

##### 管理 Workspace Asset Grant

Workspace 可以获得、调整或失去对外部 Environment 或 Shared Resource 的 Workspace Asset Grant。

Grant 表示 Workspace 使用对应顶层资源的资格，不改变资源 Ownership；创建 Run 时必须固定实际使用的具体 Version。

##### 管理 Compute Plan

Platform 可以创建、调整和停用 Compute Plan。

Compute Plan 表示面向用户的算力资源与限制组合，不直接等同于底层调度系统对象。其后续变化不得改变已有 Run Snapshot 中已经固定的执行配置。

##### 管理 Entitlement Request 与 Resource Entitlement

Workspace 可以针对 Compute Plan 提交 Entitlement Request。

请求经处理后可以创建、调整或延续 Resource Entitlement。Workspace 使用 Compute Plan 创建 Run 时，必须具有有效的 Resource Entitlement。

#### 3.4.5 Template 与 Profile 复用扩展操作

##### 管理 Template 与 Template Revision

Workspace 可以创建、维护和删除 Template，并创建不可变的 Template Revision。

Template Revision 可以作为创建 Project 的确定来源。创建后的 Project 具有独立生命周期，不受源 Template 或 Template Revision 后续状态与生命周期影响。

##### 管理 Profile 与 Profile Version

Workspace 可以创建、维护和删除 Profile，并创建不可变的 Profile Version。

Profile Version 表示某一确定的扩展定义。Profile 后续发布的新 Version 不得自动改变已有 Profile Instance。

##### 管理 Profile Instance

Workspace 可以基于确定的 Profile Version 创建 Profile Instance，并将该版本的扩展定义固化为 Instance 的 Effective Definition。

Profile Instance 可以维护 Workspace-specific Configuration，并保留 Source Profile Version 作为来源引用；其生命周期不依赖源 Profile 或 Profile Version 持续存在。

Profile Instance 可以显式切换至其他 Profile Version，并基于目标 Profile Version 重新固化 Effective Definition；不得因源 Profile 发布新 Version 而自动切换。

Workspace 可以删除不再需要的 Profile Instance。

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

系统采用模块化单体架构，主要由 API Backend 与 Background Worker 两类运行组件组成。二者共享同一套 Application、Domain 和基础设施接口，但具有不同的运行入口和生命周期。

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

### 4.4 技术选型与运行形态

| 范围 | 选型 |
| --- | --- |
| 前端语言 | TypeScript |
| 前端框架 | React |
| UI 组件与样式 | shadcn/ui + Tailwind CSS |
| 前端设计参考 | GitHub / Primer 的布局、信息层级与交互模式，不直接绑定 Primer |
| 图标 | Lucide |
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

前端使用 shadcn/ui 与 Tailwind CSS 构建界面，并参考 GitHub / Primer 的布局模式与信息层级；后端采用模块化单体架构，API Backend 与 Background Worker 共享 Application、Domain 与 Infrastructure 代码。

## 五. 工程实现规划

本章规定工程组织、实现方式和演进约束。具体 Schema、API、Port 和基础设施细节，在对应垂直切片进入开发前按需设计。

### 5.1 仓库与目录组织

项目采用 Monorepo：

```text
107-workspace/
├── frontend/
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
│   │       ├── workspace/
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

正式投产并形成兼容义务之前，`main` 表示当前有效、可运行、可验证的集成基线，而不是内部实现的永久兼容基线。

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

具体前后端工具可以不同，但本地开发、CI 和自动化统一通过项目级命令执行；`make check` 作为提交和合并前的主要验证入口。

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
当前代码事实  → main
设计决策      → Design Document / ADR
在途状态      → Journal
延后设计      → docs/product/deferred.md
协作规则      → AGENTS.md
```

## 六. 开发与迭代规划

当前开发以 Competition V1 为近期目标，以真实投产为长期目标。开发按垂直切片推进，优先验证核心执行链路，再逐步完善复用、协作与产品体验。

### 6.1 开发策略

开发顺序遵循：

```text
工程基线
→ 验证执行链路
→ 单用户计算闭环
→ Run 复用
→ 协作复用
→ Competition V1
```

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

M0 可以使用 Fake Port 验证应用结构；M1 开始优先接入真实 Worker、Git / Shared FS 和 Slurm，尽早验证核心技术可行性。

### 6.3 Milestone

Milestone 按可交付能力划分，而不是按领域模块逐个完成。

| Milestone | 目标 |
| :-------: | :---: |
| **M0 Engineering Baseline** | 建立 Monorepo、Backend、Worker、测试、配置与统一工程入口，使后端可本地运行 |
| **M1 Executable Skeleton** | 使用真实 Git / Shared FS / Slurm 打通最小 Run 执行链路 |
| **M2 Single-user Compute Loop** | 完成 Personal Workspace、Project / Version、Run Configuration、Run / Snapshot、Log / Artifact 等基本计算闭环 |
| **M3 Reusable Run** | 完善重跑、Fork、Environment、Shared Resource、Input Binding 等能力，使已验证计算工作能够复用 |
| **M4 Collaborative Reuse** | 完成 Collaborative Workspace、Membership / Role、Asset Grant、Compute Plan / Entitlement 等协作与授权能力 |
| **M5 Competition V1** | 接入必要认证和前端，完善关键流程、异常处理与演示环境，达到比赛可用状态 |

Template 与 Profile 不作为 Competition V1 的阻塞项；核心链路稳定且时间允许时，可以作为增强能力继续推进。

Gallery、Official Asset / Official Library、Course Profile、Shareable Asset 等暂不进入当前 Roadmap，继续作为延后设计事项管理。

### 6.4 迭代与范围控制

开发按照：

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
main
```

进入某个 Milestone 时再拆分具体 Issue，不提前固定整个 V1 的全部任务。

Milestone 完成时至少要求：

- 目标能力能够实际运行；
- 相关验收条件满足；
- 关键路径经过验证；
- `make check` 通过；
- `main` 保持完整、一致、可继续开发。

Roadmap 和 Milestone 可以根据实现反馈调整，但范围变化应显式更新对应记录，不在开发过程中静默扩大目标。

开发早期无保留义务的数据可以重建；进入共享演示、部署或需要保留数据的阶段后，再按照 Migration 和兼容性规则演进。

### 6.5 Roadmap

当前 Roadmap 以 Competition V1 为近期目标，不绑定具体日期，并根据实现反馈持续更新。

| Milestone | 核心目标 | 关键能力 | V1 要求 |
| :---: | :---: | :---: | :---: |
| **M0 Engineering Baseline** | 建立可持续开发的工程基线 | Monorepo、Backend、Worker、测试、配置、统一工程入口 | 必须 |
| **M1 Executable Skeleton** | 跑通最薄真实执行链路 | Run / Snapshot、Worker、Git / Shared FS、slurmrestd / Slurm、状态回写 | 必须 |
| **M2 Single-user Compute Loop** | 形成单用户完整计算闭环 | Personal Workspace、Project / Version、Run Configuration、Run、Log、Artifact | 必须 |
| **M3 Reusable Run** | 使已验证计算工作能够复用 | 重跑、Fork、Environment、Shared Resource、Input Binding | 必须 |
| **M4 Collaborative Reuse** | 支持多人协作与跨 Workspace 复用 | Collaborative Workspace、Membership / Role、Asset Grant、Compute Plan / Entitlement | 必须 |
| **M5 Competition V1** | 完成比赛可用产品形态 | USTC CAS、必要前端、关键异常流程、演示环境与整体收口 | 必须 |
| **Optional Enhancement** | 扩展项目创建与场景化复用能力 | Template、Profile... | 时间允许 |

Gallery、Official Asset / Official Library、Course Profile、Shareable Asset 等暂不进入当前 Roadmap，继续作为延后设计事项管理。

Competition V1 之后，再根据真实投产需求规划部署、监控、备份恢复、数据迁移、安全和长期运维等生产化能力。
