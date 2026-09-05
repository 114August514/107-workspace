# Issue 120 — Environment 展示与发布

- 状态：实现与验证完成，2026-09-06。
- Issue：https://github.com/114August514/107-workspace/issues/120
- 分支：feat/120-environment-publishing，基于 origin/main 286d761。

## 交付

复用 User Group / Primer 的环境上下文、导航、标题、版本列表与 About 布局。
发布入口为独立弹窗，名称和说明常显，技术定义和可选配置按需展开。
后端提供发布 capability、平台选项、公开镜像导入、真实持久阶段和重试所需输入。
上传及导入采用分块落盘与 CAS 文件写入；发布前验证 SIF 字节、架构及当前权限。
CLI 拉取在独立 user/network namespace 中，通过 Unix relay 接入公网 HTTPS CONNECT
代理；DNS 结果全量校验、数字 IP 连接，隔离回环及私网绕过。受限大小、流量、耗时和
子进程组在超时／取消时清理。已保存的候选在中断后复用，成功记录重放不产生重复版本。

## Fresh evidence

- 最终 `make check` 全部通过：后端 426 passed / 3 skipped；工具链 13 passed / 1 skipped；
  前端 38 files / 274 passed；lint、format、build、生成 OpenAPI 比对通过。
- 目标后端测试覆盖内部地址、混合 DNS、连接固定数字地址、后续重定向目的地重新校验、
  不支持来源、流式内容、摘要不符、超限、缺少工具、超时／取消的进程组清理、权限及中断恢复。
- Chromium 1440×1000 / 375×812：正式页面浏览、键盘展开、弹窗、无横向溢出／JS 错误；
  受控接口响应验证 loading / error / retry / empty / reader。
- 浏览器对正式本地 API 实际完成 Modules、上传真实 SIF、远程 OCI 导入三条发布闭环，
  从持久发布记录进入成功版本。演示标签 `review-120-1788625149-*`。
- 真实 `docker://quay.io/libpod/alpine:latest` 经 Apptainer 拉取、转换并 inspect 成功；
  独立适配器验证文件 2,752,512 bytes，SHA-256
  `1116cb4ed44e2e5efef3617e0dc8ee5bd63065b53d50b74d2d6e9cf8bc62d8a3`，架构 amd64。
  运行使用最终 SIF 摘要，不将该可变 tag 当成确定版本引用。
- 实际 namespace 中无法连接宿主机回环监听器，内部 HTTPS 目的地被代理拒绝。
- Docker Hub 在本机网络连接失败，Quay 实际成功。HTTPS 使用受控 transport 验证，
  ORAS / Library 未做公网端到端拉取；此证据不覆盖 live 107 / Slurm 或容器部署 namespace 策略。

## 截图

- [环境概览](issue120/overview-desktop.png)
- [地址导入](issue120/import-desktop.png)
- [手机发布弹窗](issue120/import-mobile.png)
- [真实发布记录](issue120/history-desktop.png)
- [手机 SIF 详情](issue120/sif-mobile.png)

## 仓外清理与保留

临时 Vite 5175 已停止，`/tmp/107-environment-design` 已删除；socket 检查确认无 5175 监听，
正式源码无临时预览入口。保留正式 Vite 5174 / API 8000 与 `/tmp/issue81-demo` 演示数据。
用户已有 `backend/uv.lock` 镜像源变更及并行出现的 design-zxb / Zone.Identifier 文件未纳入提交。
