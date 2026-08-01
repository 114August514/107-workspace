# 收敛部署文件目录

- 状态：已完成
- 认领：August / Codex
- 上下文：将活动部署编排收敛到根目录 deploy/
- 开始：2026-08-01 10:02 +0800
- 结束：2026-08-01 10:13 +0800

## 意图

建立清晰的部署文件所有权：`deploy/` 保存可执行编排，服务目录保留各自镜像构建契约，
`docs/operations/` 继续保存中文部署说明与运行边界。

## 预期改动

- 将根目录 `docker-compose.yml` 迁移为 `deploy/compose.yaml`。
- 新增中文 `deploy/README.md`，说明目录边界和跨平台入口。
- 让 Python 统一入口、CI、README 与部署文档显式使用新路径。
- 显式固定 Compose project directory，保持相对挂载路径以仓库根目录为基准。
- 更新 Doctor、文档引用测试和目录指针，并补充 CLI 回归测试。

## 仓外副作用

无。不启动或删除容器，不修改远端仓库，不发布镜像。

## 回退方式

git revert <commit>

## 验收

- CLI 路径测试先失败后通过
- `docker compose --project-directory . --file deploy/compose.yaml config`
- `make doctor`
- `make check`

## 禁区

- 不移动服务目录中的 Dockerfile、入口脚本或 Nginx 配置。
- 不把当前单机 Compose 宣称为生产部署。
- 不新增依赖，不修改应用功能或容器启动语义。

## 结果

- 根目录 `docker-compose.yml` 迁移为 `deploy/compose.yaml`；服务自己的 Dockerfile、
  后端入口脚本与 Nginx 配置仍留在对应服务目录。
- Python 统一入口、薄 `Makefile`、CI 和活动文档均显式选择新清单；Compose project
  directory 固定为仓库根目录，因此构建上下文和相对存储挂载保持原有语义。
- 新增中文 `deploy/README.md`，区分可执行编排、服务镜像契约与生产部署说明；同步
  产品设计目录图、文档拓扑 ADR、Doctor 必需文件和文档引用测试。
- CLI 回归测试先验证旧入口缺少清单参数，再随实现通过；Compose 配置、Ruff、
  Prettier 和文档引用检查均通过。
- `make doctor` 通过，确认 Node 24.18.0 与 pnpm 11.18.0；仅提示可选 hooks 未启用。
- `make check` 通过：工作流 11 项、后端 270 项、前端 61 项，以及 lint、格式、类型、
  构建和 API Contract 全部通过。
- 前端构建仍报告约 1.29 MB 主 chunk 警告，本次部署目录整理未处理该既有性能事项。
- 未启动或删除容器，未修改远端仓库，也未发布镜像。
