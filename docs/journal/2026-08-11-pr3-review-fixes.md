# PR #3 Review 修复

- 状态：待复审
- 认领：August / Codex
- 上下文：分支 `feat/3-shared-resource-core`，修复 CHANGES_REQUESTED review
- 开始：2026-08-11
- 关联：PR #3（Closes #4）

## 意图

PR #3 收到 3 项必须处理 + 2 项非阻塞。本分支逐一处理：

1. **Platform SR 作 Run Input 绕过 Asset Grant（GR-401）**：`_check_shared_resource_version_input`
   对 `is_platform_owned` 直接放行。本 PR 阶段**拒绝** Platform SR 作 Run Input，等 M4 Asset Grant。在 M4 Asset Grant 实现前，不允许 Platform Shared Resource 作为 Run Input，避免形成 GR-401 之外的授权路径。
2. **`source_subpath` 契约有、执行时被忽略**：结构性原因——`RunInput` 无 `source_subpath` 字段，物化整版。design.md §3.1.3 把它设计成 Input Binding 的可选子路径过滤。**实现** subpath 过滤。实现和复核过程中确认并处理以下边界：：
   - B1 缺 `posixpath.normpath` → 静默零文件物化（关键）
   - B2 frozen dataclass 须 `object.__setattr__`
   - B3 单文件 subpath 剥前缀到空串 → `copyfile` 到目录崩（关键，须保留 basename）
   - B4 Artifact 分支须分文件/目录 + resolve 防御
   - B5 preflight 签名加 subpath，两个调用点都改（rerun 白捡）
   - B6 符号链接（现有、不扩面）
   - B7 access_path 未 normpath（现有、不扩面）
3. **领域对象单元测试缺失**：补 `SharedResource`/`Version`/`File` 可变性 + 派生属性 + `_normalize_path` 路径单测（application 层，参考 `test_project_paths.py`）。

## 非目标

- 不实现 Workspace Asset Grant（M4）
- 不改 migrations 逻辑（只加 downgrade 注释）、不改 AccessGuard/Capability enum
- 不动 Artifact 模型加文件清单
- 不碰 #5 前端（已 stash 隔离）

## 验证

- `make check backend` 全绿。
- 原有 5 个不传 `source_subpath` 的闭环测试保持通过，既有行为不变。
- Review 中提出的 3 项必须处理问题均已完成代码修复。
- 当前等待最终复审；PR 合并后再将本记录移入归档。
