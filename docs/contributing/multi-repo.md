# 多仓库协作

## 仓库与文档归属

107-workspace 是索引和集成仓库，backend/、frontend/ 是 Git 子模块。
107-backend 与 107-frontend 可独立克隆、安装、检查、构建和发布。
本次仅改变工程归属，不拆分后端服务或改变 API、权限、数据库行为。

产品设计、跨组件 ADR、平台运维和整体测试策略仍由本仓库 docs/ 维护。
组件 README、组件测试与构建、契约生产或消费说明随组件维护。
不新建 docs 仓库，避免让每次产品调整额外协调第四个仓库。
代码中的 docs/ 与 GR/ADR 引用指向索引仓库的文档命名空间。

## 日常开发

完整联调先递归克隆索引仓库；已有 clone 使用：

```bash
git submodule update --init --recursive
make setup
make check
```

子模块初始为 detached HEAD。开发前在相应仓库创建分支：

```bash
git -C backend switch -c feature/my-change
# 修改并执行 backend/make check（即 cd backend 后 make check）
git -C backend add <本次修改的文件>
git -C backend commit -m "说明组件变化"
git -C backend push -u origin feature/my-change
```

组件 PR 合并后，在索引仓库选定已推送的提交，运行集成检查，再提交子模块指针。
不要在索引仓库提交指向仅存在于个人电脑的组件提交。
更新子模块前先检查本地修改；不要强制覆盖工作区。

## API 变化

1. 后端修改路由与 DTO，执行 `make contract` 和 `make check`，提交并推送。
2. 前端获取选定后端提交的 contracts/openapi.json，保存为本仓库的同名快照。
3. 更新 contracts/source.json 的 commit、sha256，working_tree_dirty 必须为 false。
4. 前端执行 `pnpm run generate:api` 和 `make check`，提交并推送。
5. 索引仓库更新两个子模块指针并运行 `make check`。

完整工作区也可执行根目录 `make contract` 一次生成整条链路。
来源记录区分后端已提交版本与未提交工作区；正式集成前先提交后端，再重新同步契约。
独立前端检查验证消费快照与生成类型；集成检查进一步核对选定后端导出的契约。

## 发布与部署

前后端各自使用组件仓库的 Release workflow 发布镜像，保留 annotated tag 和
SemVer 校验。镜像分别为 ghcr.io/114august514/107-backend 与
 ghcr.io/114august514/107-frontend（实际 tag 由发布版本决定）。
索引仓库不再统一构建和发布两个组件的版本；其提交记录一套经过集成验证的源码组合。
Compose 本地构建继续使用固定子模块源码。使用已发布镜像时在本地环境设置
WORKSPACE107_IMAGE_API 与 WORKSPACE107_IMAGE_WEB 为明确版本或 digest，
然后使用 `docker compose --project-directory . --file deploy/compose.yaml up -d --no-build`。
不要把 latest 当作可复现部署版本；更新接口时应考虑已运行的旧客户端。

## 历史与回退

组件仓库用 git subtree split 提取各自目录历史，作者与提交说明保留，提交 SHA 会变化。
索引仓库保留原始完整历史、Issue 和 PR 链接，不重写共享历史。
回退某个集成版本时检出相应索引提交，再执行 git submodule update --init --recursive。
这只切换代码，不代表数据库迁移可逆；持久化回退继续遵循运维规范。

## Issue 与任务归属

- 单组件实现和缺陷在对应组件仓库维护；跨组件产品目标、部署与整体验收在索引仓库维护。
- 使用跨仓完整链接或 `owner/repo#number`；裸编号只引用当前仓库。
- 转移前先核对实现和验收：已完成项关闭并保留原历史，部分完成项明确剩余工作。
- 父任务记录完整用户结果，子任务记录具体交付；拆出子任务不等于完成父任务。
- [Core 索引](https://github.com/114August514/107-workspace/issues/43) 和
  [V1/Optional 索引](https://github.com/114August514/107-workspace/issues/53) 作为跨仓入口，
  不再复制一份独立的全量 Markdown backlog。

首次整理的映射和证据见 [2026-09-16 审计记录](../archive/2026-09-16-issue-audit.md)。
