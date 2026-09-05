# Simple Run 验证

基于 `feat/81-simple-run`，本地 Chromium，真实 Vite + API + 临时 SQLite + Mock Scheduler。
演示数据仅位于 `/tmp/issue81-demo`，不使用真实凭据或集群资源。

- 桌面 1440 × 1000、窄屏 375 × 812；精简编辑、展开高级设置、确认摘要均无横向溢出。
- 键盘 Enter 打开、Tab 切换字段、Enter 展开高级设置、Escape 关闭并归还入口焦点。
- 浏览器实际创建方案，将 CPU 调整为 3 后折叠资源区，提交后 Snapshot 仍记录 3 CPU。
- Run `run_4efd0487c65a4061917e` 在真实本地子进程中 succeeded：stdin 读取到 EOF，stdout/stderr 均可从日志接口读取，收集 `outputs/result.txt` 为一个运行产物。
- `editor-*`、`advanced-375.png`、`submit-*`、`run-result.png` 为上述流程截图。
- 空列表及请求失败截图通过浏览器 HTTP 边界替换响应获得；不代表真实网络故障。验证了失败时禁用提交和重试恢复。

Slurm 的 batch I/O 证据来自 `backend/tests/integration/scheduler/test_slurm_batch_io.py` 的 HTTP transport 测试及生成脚本；未连接真实 Slurm，不声明完成 #7 的真实环境验收。

合入 main（`d28f934`）后完整 `make check` 通过：后端 393 passed、3 skipped；前端 272 passed；代理测试 13 passed、1 skipped；生产构建与生成契约检查通过。

交互评审后的 `revised-*` 截图记录名称与说明常显、小标题字号、带边框的删除按钮、默认折叠的资源区及命令换行、集中操作菜单。截图使用本地演示数据，已在合入最新 main 后重新验证和截图。

下拉高亮修正：`revised-select-*` 区分已选项勾选标记与蓝色 hover / 键盘焦点。截图中的第二项仅为浏览器 DOM 临时测试选项，未保存到 API。Chromium 实测 hover、移开恢复、键盘选择、Escape 仅关闭下拉和窄屏布局。使用 CSS `appearance: base-select` 渐进增强；不支持此能力的浏览器保留系统原生下拉样式，不保证相同配色，参见 [MDN](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms/Customizable_select)。
