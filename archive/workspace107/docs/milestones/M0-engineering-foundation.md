# M0 - Engineering Foundation

## 目标

让任意一位新成员能在半小时内把仓库跑起来，并按统一流程提交第一个 PR。

## 用户结果

这里的「用户」是团队成员本身。完成 M0 后：

```text
克隆仓库 → 安装依赖 → 本地启动 → 建分支 → 提交 → 开 PR → CI 自动检查
```

整条链路不需要口头传授，也不依赖某一个人的本地环境。

## 范围

- 仓库骨架：`backend/`、`frontend/`、`docs/`、`scripts/`
- 换行与编码规范：`.gitattributes`、`.editorconfig`
- 忽略规则与密钥纪律：`.gitignore`、`.env.example`
- 协作规范：`CONTRIBUTING.md`、`docs/development/*`
- GitHub 模板：Issue 模板、PR 模板、CODEOWNERS
- CI：`backend-lint`、`backend-test`、`frontend-lint`、`frontend-typecheck`、
  `frontend-test`、`api-contract-check`
- 本地一键自检脚本 `scripts/check.sh`
- 领域语言与全局不变量文档

## 非目标

- 业务功能实现（属于 M1）
- 容器化部署与生产环境编排
- 数据库迁移检查、安全扫描、端到端测试等进阶 CI
- 权限模型的完整实现

## 完成标准

- [x] `git clone` 后按 `CONTRIBUTING.md` 能完成安装和启动
- [x] `.env.example` 只有变量名和说明，仓库中不存在任何真实凭据
- [x] `scripts/check.sh` 与 CI 执行同一组命令
- [x] Issue 和 PR 模板强制填写关联 Issue、验证方式和影响范围
- [x] 分支命名、Commit 格式、评审顺序有书面规范
- [x] 领域语言和全局不变量已文档化，评审时可对照检查
