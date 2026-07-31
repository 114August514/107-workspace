# ADR-0002 Shared Resource 的归属、版本与跨空间授权

状态：已接受 · 阶段：M2 · 相关：GR-004、GR-007、GR-008、GR-011、GR-013

## 背景

设计稿 §2.6 和 §3.2.10 定义了共享资源：独立于 Project 存在、可版本化、
可授权给多个 Workspace 使用的内容资源。典型场景是一份课程数据集，
三十个学生的 Project 都要读它，但不该每人复制一份。

M1 已经实现了 Input Binding，但只支持 `artifact` 来源。M2 要补上
`shared_resource_version`，同时解决授权问题。

需要定下来的是：

1. 资源归谁？授权怎么表达？
2. 撤销授权时，正在跑的和已经跑完的 Run 怎么办？
3. 没被授权的人，看得见这个资源存在吗？
4. 内容存哪儿？和集群的 `/public` 是什么关系？

## 决策

### 1. 资源归属一个 Workspace（或平台），版本不可变

```text
Shared Resource                  可变：名称、说明、推荐版本、授权配置
└── Shared Resource Version      不可变：一组 (path, size, content_hash)
```

和 Project Version 用同一套内容寻址存储。发布新版本 = 新建一组记录，
不修改任何已有版本（GR-003）。

### 2. 授权是 Workspace 对 Workspace 的显式关系

```text
Workspace Asset Grant
├── 资源标识
├── 被授权的 Workspace
├── 授权范围（只读）
├── 授权人与时间
└── 可选的到期时间
```

**授权对象是 Workspace，不是 User。** 理由：Membership 只在对应 Workspace 内生效
（GR-001），把资源授权给个人会绕开这条边界——那个人换个空间就能带走访问权。
授权给 Workspace 之后，谁能用取决于谁是这个 Workspace 的成员，
边界和其他对象保持一致。

拥有者自己的 Workspace 天然有权使用，不需要给自己发一条授权。

### 3. 撤销授权不动历史，但拦住未来

这是 GR-007 和 GR-008 的直接应用，也是最容易写错的地方：

```text
撤销授权后

已完成的 Run
├── Run Snapshot 里的 Input Binding 记录原样保留
├── 详情页仍然显示「曾经使用过 dataset-v2」
└── 但点进去看内容 → 403 / 404，历史事实不等于当前访问权

正在排队或运行的 Run
└── 不中断。快照已经固定，输入内容已经准备好了

新提交的 Run
└── 提交前检查直接拦下：「输入 X 引用的共享资源不存在或无权访问」
```

M1 的 `_check_inputs` 已经是这个形状，M2 只是把来源类型从 artifact 扩展到
shared resource version。

### 4. 无授权即不存在

按 GR-013，没有发现权限时：

```text
搜索结果里不出现
列表里不出现
直接用 ID 访问 → 404，不是 403
错误信息不区分「不存在」和「无权访问」
```

M1 已经在 `AccessGuard` 里立了这个规矩（无权访问抛 `ObjectNotFound`），
共享资源沿用同一套，不另起一套判断。

「可发现但需要申请」（§2.6 D，V2）是后续能力。M2 只有两种状态：
**有授权就能用，没授权就当它不存在**。

### 5. Input Binding 不为新来源另起结构

设计稿 §3.1.3 已经写清楚了：Shared Resource Version 和 Artifact 都提供
Content Version，Input Binding 统一引用一份确定内容。

M1 的结构原样保留，只是 `source_type` 多一个取值：

```text
InputBinding
├── source_type      artifact | shared_resource_version
├── source_id
├── source_subpath   可选
└── access_path      在 Run 中暴露的路径
```

好处很直接：解析、校验、准备工作目录、写进快照这几段代码一行都不用分叉。

### 6. 内容只读提供，与集群共享存储的关系留作部署配置

按 GR-011，共享资源以只读方式提供给 Run。具体怎么"提供"由 RuntimeBackend 决定
（见 [ADR-0004](0004-runtime-backend.md)）：

```text
Native / Conda    平台把内容放到 Run 目录下，通过 $WORKSPACE107_INPUTS_DIR 暴露
Apptainer         apptainer exec --bind <宿主路径>:<access_path>:ro
```

**和 `/public` 的关系不写死。** 平台的共享存储路径策略、配额和目录约定属于
动态平台事实，需要向平台方确认。领域层只认 `StoragePort`，
真实部署时换成指向共享文件系统的实现即可。文档里一律写「以平台页面为准」。

### 7. 大内容不复制字节

和 Fork 一样（[ADR-0001](0001-fork-semantics.md) 第 5 条），
共享资源版本只是一组 `(path, hash)` 记录。三十个 Project 引用同一个数据集版本，
存储里只有一份内容。

准备 Run 工作目录时，对大目录应当用**只读绑定挂载或符号链接**，
而不是 M1 现在的 `shutil.copytree`。M1 的复制实现对演示够用，
但一份 50 GB 的数据集每次 Run 都复制一遍是不可接受的——
这一点要在 Issue 里明确写出来，别默认沿用。

## 放弃的方案

**把共享资源做成一种特殊 Project。** 看起来能复用一堆代码，但语义是错的：
Project 是可编辑、可运行的工作对象，共享资源是不可变的内容供给。
混在一起之后「能不能对数据集提交 Run」这种问题就没有干净答案了。

**授权给用户而不是 Workspace。** 见第 2 条，会绕开 Workspace 边界。

**撤销授权时级联清理已有 Run 的记录。** 直接违反 GR-016：删除不能重写历史事实。
而且会让「这次实验到底用了什么数据」这个问题永远失去答案。

**每次 Run 都把数据集复制进工作目录。** 见第 7 条。

## 影响

- 新增领域对象：`SharedResource`、`SharedResourceVersion`、`AssetGrant`
- `StoragePort` 需要新增只读挂载能力，不能只有 `copytree`
- `_check_inputs` 与 `_revalidate_snapshot` 都要扩展到新来源类型，两处都要有测试
- 数据清理要考虑「资源被别的 Workspace 引用中」的情况，删除前必须做影响检查（GR-016）
- 「将 Artifact 发布为共享资源」（§2.6 C，V1）会用到同一套版本发布逻辑，
  设计时留好入口
