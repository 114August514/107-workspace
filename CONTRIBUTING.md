# 参与开发

本文件只提供入口，完整规则以
[`docs/contributing/git-workflow.md`](docs/contributing/git-workflow.md) 为准，产品术语与
领域约束以 [`docs/product/design.md`](docs/product/design.md) 为准。

## 开始之前

1. 用 Issue 写清背景、目标、范围、验收条件和非目标。
2. 从 GitHub 当前默认分支创建符合 Git 协作规范命名规则的短期分支。
3. 阅读根目录 `AGENTS.md` 和改动目录附近的说明。
4. 跨会话、多人并行或有仓外副作用的工作，在 `docs/journal/` 记录状态。

## 本地工作流

```bash
make setup
make check
```

Windows 不要求安装 Make：

```powershell
uv run --no-project python scripts/workspace.py setup
uv run --no-project python scripts/workspace.py check
```

修改 API DTO 或路由后运行 `make contract`，并提交
`contracts/openapi.json` 与 `frontend/src/api/schema.d.ts` 的对应变化。

提交前检查 `git status` 和暂存区 diff，只提交与当前 Issue 相关的文件。不要提交
`.env`、密钥、数据库、用户文件、Run 输出、虚拟环境、依赖目录或构建产物。

## 评审重点

- 验收条件是否真正满足，异常路径是否有测试。
- Workspace 归属与权限过滤是否落在服务和数据访问边界。
- Version、Revision、Run Snapshot 和 Artifact 的不可变语义是否保持。
- Secret 明文是否可能进入 Snapshot、日志、响应或前端状态。
- 生成契约是否同步，数据库迁移是否实际验证升级、回退和再升级。
- 涉及调度、共享存储或运行环境时，说明验证的是 Mock 还是真实基础设施。
