# Commit 与 PR 标题规范

## 一. 格式

```text
<类型>(<范围>): <一句话说明>
```

范围可以省略（例如纯文档改动），类型和说明不能省略。说明使用中文，不加句号。

## 二. 类型

| 类型 | 用途 |
| :--- | :--- |
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `refactor` | 不改变行为的重构 |
| `test` | 测试 |
| `docs` | 文档 |
| `chore` | 工程配置、依赖、CI |

## 三. 范围

按领域和技术分层取值：

```text
workspace    project     run         storage
slurm        resource    auth        api
web          cli         docs        ci
```

新增范围前先确认现有范围是否够用，避免每个人发明一套。

## 四. 示例

推荐：

```text
feat(workspace): 支持邀请空间成员
fix(run): 修复取消作业后状态未更新
refactor(slurm): 提取统一命令执行接口
test(project): 补充项目归档服务测试
docs: 补充本地开发环境说明
chore(ci): 增加后端 Ruff 检查
```

不要写：

```text
update        修改一下        fix bug
final         提交代码        完成工作
```

## 五. 粒度

一个 Commit 只表达一个逻辑变化：

```text
实现一个功能              → 一个 Commit
完成一次独立重构           → 一个 Commit
补充一组对应测试           → 一个 Commit
```

开发分支中允许出现「补测试」「修复 lint」「处理 review」这类中间提交，
因为 PR 采用 Squash merge，合并后 `main` 上只留下一条：

```text
feat(workspace): 支持创建协作空间 (#123)
```

## 六. PR 标题

PR 标题使用同样的格式，因为它就是 Squash 之后写入 `main` 的提交信息。
