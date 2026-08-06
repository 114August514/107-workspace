# 107 Workspace 新手开发指南

这份指南面向已经学过变量、函数、类等基本编程概念，但还没有参与过完整 Web 或计算集群
项目的读者。目标不是把每项技术讲透，而是帮助你建立一张足够准确的地图，能够启动项目、
读懂一次 Run 的主链路，并在现有规范下完成一个小改动。

## 阅读目标

读完并完成练习后，你应当能够：

- 说清浏览器、API、数据库、文件存储和 Slurm 之间的关系；
- 在本地安装依赖、迁移数据库并启动前后端；
- 判断一段后端代码应属于 API、Application、Domain 还是 Infrastructure；
- 沿 OpenAPI 契约找到前后端字段的来源；
- 理解 Run 的创建、提交、轮询、日志和 Artifact 流程；
- 为小改动添加测试，并通过仓库统一检查后提交 Pull Request。

## 知识边界

本指南只讲参与本项目日常开发所需的部分。它不是 Python、React、数据库、Docker 或
Slurm 的完整教程，也不是集群管理员手册。遇到下列主题时，正文只说明它们在项目中的
作用和使用入口：

- Python 事件循环、数据库执行计划等底层原理；
- React 性能优化和复杂状态管理；
- Slurm 安装、调度策略和集群管理员配置；
- Kubernetes、高可用、监控平台和完整生产安全体系。

## 阅读顺序

第一次阅读建议按顺序进行。已经熟悉 Web 开发的读者可以快速浏览前三章，再从自己负责的
部分开始。

1. [项目与业务概览](01-project-overview.md)
2. [从一次 Run 看懂系统](02-run-through-system.md)
3. [搭建开发环境](03-development-environment.md)
4. [仓库结构与系统架构](04-architecture.md)
5. [Python 后端开发](05-backend.md)
6. [React 前端开发](06-frontend.md)
7. [数据库与接口契约](07-database-contract.md)
8. [Slurm 开发必备知识](08-slurm.md)
9. [测试、质量检查与调试](09-testing-and-debugging.md)
10. [Git 与团队协作](10-git-workflow.md)
11. [容器、部署及其边界](11-deployment.md)
12. [完成第一个小改动](12-first-change.md)
13. [附录：常用速查](appendix.md)

## 如何判断资料是否仍然有效

仓库中的资料有明确优先级：

1. 当前产品能力、术语和业务规则以 [`../../product/design.md`](../../product/design.md) 为准；
2. 已接受的高影响技术决定记录在 [`../../decisions/`](../../decisions/README.md)；
3. 代码和服务目录 README 说明当前实现；
4. `docs/references/` 只是参考输入；
5. `archive/` 和 `docs/archive/` 只用于追溯历史。

如果历史材料与当前产品设计冲突，以活动产品设计和活动 ADR 为准。当前仓库是可运行的开发
基线，不代表产品路线图中的所有能力已经完成。

## 文中的命令约定

除非特别说明，命令都在仓库根目录 `107-workspace/` 执行。POSIX 示例使用 Bash。
Windows 没有 GNU Make 时，可以使用同一个 Python 任务入口，例如：

```powershell
uv run --no-project python scripts/workspace.py check
```

命令中的 `<project_id>` 等尖括号内容是占位符，需要替换成真实值，不要连同尖括号一起输入。
