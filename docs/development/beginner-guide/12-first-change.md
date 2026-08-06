# 第十二章：完成第一个小改动

第一次贡献的目标不是展示能改多少代码，而是完整走通“理解任务、写测试、实现、验证、提交”
这条链。下面以一个低风险任务为例：为前端时长格式化函数补充边界行为。

> 这是流程练习，不表示仓库当前存在对应 Issue。正式开发必须先领取真实 Issue，并以其验收条件
> 为准。

## 12.1 为什么选择这个练习

`frontend/src/utils/format.ts` 包含 `formatDuration()`，Run 列表用它展示排队和运行时间。这个
练习具备几个优点：

- 输入输出明确，不需要启动 Slurm；
- 不涉及数据库迁移、认证、Secret 或依赖新增；
- 可以用 Unit Test 快速完成红、绿、重构循环；
- 改动虽小，却会沿真实页面被用户看到。

假设 Issue 给出如下验收条件：

```text
目标：负数时长按未知值展示，避免页面出现“-3 秒”。

验收条件：
- null 和 undefined 仍显示“—”；
- 负数显示“—”；
- 0 至不足 1 秒仍显示“< 1 秒”；
- 其他已有格式不改变。

非目标：不修改后端字段，不改变时长计算方式。
```

## 12.2 开始前先搜

```bash
rg -n "formatDuration" frontend
```

阅读函数、调用位置和现有测试。确认仓库或依赖中没有已经解决同一问题的帮助函数。然后检查
工作区：

```bash
git status
```

真实任务还需要按 Issue 建分支；如果工作会跨会话，先创建 Journal。不要覆盖工作区中不属于
你的改动。

## 12.3 先添加测试

如果尚无对应测试文件，可在 `frontend/tests/unit/utils/` 下按需创建，例如
`format.test.ts`。目录只有在真的有测试时才创建。

测试可以写成：

```ts
import { describe, expect, it } from 'vitest'

import { formatDuration } from '../../../src/utils/format'

describe('formatDuration', () => {
  it('缺少或非法的时长显示为未知', () => {
    expect(formatDuration(null)).toBe('—')
    expect(formatDuration(undefined)).toBe('—')
    expect(formatDuration(-3)).toBe('—')
  })

  it('保留正常时长的展示', () => {
    expect(formatDuration(0)).toBe('< 1 秒')
    expect(formatDuration(65)).toBe('1 分 5 秒')
  })
})
```

先只运行相关前端测试，并确认负数断言失败。测试必须因为缺少目标行为而失败，而不是因为导入
路径、语法或环境错误。

仓库推荐通过统一入口执行检查；开发中也可以使用服务 README 记录的局部测试命令缩短反馈，
但提交前仍要回到根目录运行完整入口。

## 12.4 写最小实现

回到 `formatDuration()`，在现有空值判断中加入负数条件：

```ts
if (seconds === null || seconds === undefined || seconds < 0) return '—'
```

不要借机重写整个格式化模块、升级 dayjs 或修改所有文案。一个 PR 只处理一个主要问题，能让
Review 更快发现真实行为变化。

再次运行相关测试，确认新旧断言都通过。然后运行：

```bash
make check-frontend
```

## 12.5 手工验证调用位置

纯函数测试通过后，仍要知道它怎样进入界面。沿搜索结果查看 `RunTable.tsx`，确认排队和运行列
确实调用这个函数。若能用开发数据构造该边界，则在页面验证；如果后端正常情况下不会返回负数，
记录这是防御性展示行为，不要为了截图污染数据库。

这个练习没有修改 API，所以不需要运行 `make contract`。判断规则是：只有后端路由、Schema、
状态码、媒体类型或错误契约变化时才同步契约，不能每次前端改动都制造生成文件噪声。

## 12.6 完整检查和差异审阅

提交前运行：

```bash
make check
git status
git diff
```

逐行检查：

- Diff 是否只包含测试和最小实现；
- 是否意外加入 `node_modules`、日志或 `.env`；
- 测试是否准确描述边界；
- 是否保留已有正常行为；
- `make check` 的实际结果是否成功。

只暂存本次文件，并再次查看暂存差异：

```bash
git add frontend/src/utils/format.ts frontend/tests/unit/utils/format.test.ts
git diff --staged
```

## 12.7 Commit 和 PR

Commit 示例：

```bash
git commit -m "fix(web): 处理负数 Run 时长"
```

PR 描述可以很短，但证据要具体：

```markdown
## 关联 Issue

Closes #123

## 修改内容

- 负数 Run 时长显示为未知值。
- 补充空值、负数和正常时长单元测试。

## 验证证据

- `make check`：通过。

## 影响范围

- 仅前端展示，不修改 API 和数据库。
```

完成这个练习后，你已经经历了项目日常开发的最小闭环。接下来可以逐步尝试带 API 字段的前后端
改动，再进入数据库、权限或调度功能；不要把高风险模块当作第一个练习。

## 12.8 功能改动的通用检查表

以后面对更完整的功能，可以按下面顺序自查：

```text
[ ] 阅读 Issue、产品术语和相关 ADR
[ ] 先搜现有代码和测试
[ ] 建立或更新 Journal
[ ] 明确权限、不可变性和 Secret 风险
[ ] 写测试并看见预期失败
[ ] 按层实现最小改动
[ ] API 变化时运行 make contract
[ ] 数据库变化先取得许可并验证迁移升降级
[ ] 手工走通成功、错误和越权路径
[ ] 运行 make check
[ ] 审阅 Diff，记录实际证据和未验证项
```

