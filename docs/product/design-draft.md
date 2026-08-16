> **历史对比稿，非当前产品权威。** 当前产品设计以 [`design.md`](design.md) 为准。

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

### 2.8 Run 生命周期与
[…1566ln elided…]
 的变化只影响对应 User 在该 Workspace 中的成员身份和操作权限，不改变 Workspace 已有对象、资源资格及其他 Membership。

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
| 包管理器 | **pnpm 11** | 依赖安装、脚本执行及前端 Workspace 管理 |
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
| 端到端测试 | **Playwright** | 测试登录、Workspace 管理、Run 提交等完整业务流程 |

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

具体前后端工具可以不同，但本地开发、CI 和自动化统一通过项目级命令执行。`Makefile`是薄入口；原生 Windows 没有 Make 时，使用 `uv run --no-project python scripts/workspace.py check` 执行同一份任务实现。

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
当前默认分支
```

进入某个 Milestone 时再拆分具体 Issue，不提前固定整个 V1 的全部任务。

Milestone 完成时至少要求：

- 目标能力能够实际运行；
- 相关验收条件满足；
- 关键路径经过验证；
- `make check` 通过；
- 当前默认分支保持完整、一致、可继续开发。

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


Wall time: 0.03 seconds

[Showing lines 1-617 and 2184-2799 of 2799; 1,566 middle lines (53.8KB) elided. Read artifact://1500 for full output]