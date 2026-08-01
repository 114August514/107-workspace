# 迁移前目标仓库

带注释 tag `archive/pre-workspace107-migration-2026-08-01` 固定了迁移前目标实现：

- Commit: `70854351290d6184fb7cbe1e5db5bb2b5285ebb1`
- Tag message: `Archive 107 Workspace before workspace107 migration`

查看完整树：

```bash
git show archive/pre-workspace107-migration-2026-08-01^{tree}
```

该工作区当时存在一条未完成且测试失败的 `transfer -> execution_data` 重构；其范围、
状态和放弃理由保存在
[`transfer-execution-data-wip.md`](transfer-execution-data-wip.md)。这份目录只保存迁移
元数据，完整源码由 tag 提供。
