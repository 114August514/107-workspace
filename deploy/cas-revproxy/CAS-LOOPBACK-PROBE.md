# CAS 回环 service 探测（2026-09-05）

探测入口：`https://passport.ustc.edu.cn/login?service=http://127.0.0.1:8107/login`

出站代理：`http://127.0.0.1:27997`

结果：

1. `passport.ustc.edu.cn` 返回 `302` 到
   `https://id.ustc.edu.cn/cas/login?service=http://127.0.0.1:8107/login`。
2. `id.ustc.edu.cn` 返回 HTTP 200 错误页，而不是登录表单。
3. 页面错误码 `1510051`，文案为「应用未对接认证服务 / 您访问的应用尚未接入统一身份认证，请联系相关部门完成对接配置」。
4. 将 service 换成 `https://127.0.0.1:8107/login` 时，passport 同样 302 到 id.ustc.edu.cn；该回环 HTTPS 地址在本机并不提供 TLS，不能作为可交付回调。

结论：USTC CAS 当前拒绝未登记的回环 callback。真实登录闭环需要学校侧登记的 HTTPS 回调入口后再验收。第三方 HTTP 回跳页不作为交付链路。
