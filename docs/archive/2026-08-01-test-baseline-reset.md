# 重置测试基线

- 状态：已完成
- 认领：August / Codex
- 上下文：删除绑定旧实现的测试，避免它们被协作者误认为未来重构契约
- 开始：2026-08-01 15:53 +0800
- 结束：2026-08-01 16:22 +0800

## 意图

当前前后端实现是后续重构的旧基线。保留纯领域规则、平台适配与仓库治理测试，删除依赖
旧 API、进程内 Run 同步、旧权限矩阵和 Ant Design 视觉偏好的测试；未来切片实现时按照
目标设计重新建立 Application、Worker、API、组件和系统测试。

## 预期改动

- 建立按测试边界组织的前后端目录。
- 防止从仓库根目录运行 pytest 时收集 `archive/` 来源快照。
- 删除旧 ASGI / SQLite 工作流与旧 UI 测试，不保留 skip、xfail 或占位测试。
- 将覆盖率命令改成报告模式，移除重构期失真的全仓 90% 门槛。
- 用中文文档记录测试粒度、保留范围和新增测试时机。

## 仓外副作用

无。不 push，不修改远程设置。活动测试数量和当前旧实现的覆盖率会显著下降，这是本次
显式重置的结果，不表示新口径已经获得测试覆盖。

## 回退方式

回退本任务提交；旧测试仍可从 `archive/workspace107/` 和 Git 历史取回。

## 验收

- 仓库根目录与统一入口都只收集活动后端测试。
- 保留的前后端测试通过。
- `make coverage` 生成报告但不执行覆盖率门槛。
- `make check`。
- `make journal`。

## 禁区

- 不修改 `docs/product/design.md`；Git 指南仅按已确认范围修正一条失效测试路径。
- 不修改 `archive/` 来源快照。
- 不修改产品、API 或业务实现来迁就保留测试。
- 不新增尚未实现功能的占位、skip 或 xfail 测试。

## 结果

- 根目录 `pytest.ini` 将活动收集范围限定为 `backend/tests`，不再误收集
  `archive/workspace107/` 来源快照。
- 后端按 domain、application、observability、storage、scheduler 和 architecture 边界保留
  10 个测试文件，共 98 项；旧 API、SQLite 工作流、角色矩阵和安全主题测试已删除，
  依赖方向与文档引用等稳定架构门禁继续保留。
- 前端只保留 API client 与 unresolved 纯逻辑测试，共 2 个文件、14 项；旧 UI、主题门禁、
  jsdom 与 Ant Design 测试设置已删除。
- 保留测试的函数名统一改为英文 snake_case，中文只留在说明、注释与断言文本；活动测试
  不再包含 skip、skipif 或 xfail。
- 测试规范记录在 `docs/testing/README.md`；不保留 skip、xfail 或未来功能占位测试，
  新口径随重构切片重新建立。
- `make coverage` 改为报告模式，当前总覆盖率为 25%，重构期不执行失真的全仓门槛。
- 经维护者确认，Git 指南中的一条失效测试路径已改为当前仍存在的领域测试路径；
  `docs/product/design.md` 与 `archive/` 来源快照未修改。
- `make check` 全部通过，包括工作流 14 项、后端 98 项、前端 14 项、生产构建和
  OpenAPI 契约比对。构建仍报告约 1.29 MB 主 chunk 警告，本任务按既定范围不处理。
