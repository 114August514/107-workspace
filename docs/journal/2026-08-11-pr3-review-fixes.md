# PR #3 Review 修复

- 状态：进行中
- 认领：August / Codex
- 上下文：分支 `feat/3-shared-resource-core`，修复 CHANGES_REQUESTED review
- 开始：2026-08-11
- 关联：PR #3（Closes #4）

## 意图

PR #3 收到 3 项必须处理 + 2 项非阻塞。本分支逐一处理：

1. **Platform SR 作 Run Input 绕过 Asset Grant（GR-401）**：`_check_shared_resource_version_input`
   对 `is_platform_owned` 直接放行。本 PR 阶段**拒绝** Platform SR 作 Run Input，等 M4
   Asset Grant（用户拍板：收紧、不放权）。这是改现有授权代码，已获用户确认。
2. **`source_subpath` 契约有、执行时被忽略**：结构性原因——`RunInput` 无 `source_subpath`
   字段，物化整版。design.md §3.1.3 把它设计成 Input Binding 的可选子路径过滤。**实现**
   subpath 过滤（用户拍板）。经对抗式 Plan agent 验证，修正 7 处问题：
   - B1 缺 `posixpath.normpath` → 静默零文件物化（关键）
   - B2 frozen dataclass 须 `object.__setattr__`
   - B3 单文件 subpath 剥前缀到空串 → `copyfile` 到目录崩（关键，须保留 basename）
   - B4 Artifact 分支须分文件/目录 + resolve 防御
   - B5 preflight 签名加 subpath，两个调用点都改（rerun 白捡）
   - B6 符号链接（现有、不扩面）
   - B7 access_path 未 normpath（现有、不扩面）
3. **领域对象单元测试缺失**：补 `SharedResource`/`Version`/`File` 可变性 + 派生属性
   + `_normalize_path` 路径单测（application 层，参考 `test_project_paths.py`）。

## 非目标

- 不实现 Workspace Asset Grant（M4）
- 不改 migrations 逻辑（只加 downgrade 注释）、不改 AccessGuard/Capability enum
- 不动 Artifact 模型加文件清单
- 不碰 #5 前端（已 stash 隔离）

## 验证

`make check backend` 全绿 + 不破坏现有 5 个闭环测试（不传 subpath，行为不变）。
不 push、不 merge，用户确认后再说。
