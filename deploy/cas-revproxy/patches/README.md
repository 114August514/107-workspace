# 上游补丁

上游仓库：https://github.com/zzh1996/ustccas-revproxy

不要向该仓库推送。服务器上的 `/home/zxbq/ustccas-revproxy` 可直接用本仓库
`auth/auth_server.py` 覆盖其 `auth/auth_server.py`。

相对上游 `master`（`7b7f7ce`）的主要差异：

- `/auth` 返回 `X-User-ID` Header，不再把用户名写在响应体。
- `GET /login` 使用固定 `PUBLIC_ORIGIN` 作为 CAS service，不再用 `request.base_url`
  或第三方 HTTP 回跳页。
- 登录回调保留 session `id` 关联校验；失败返回 401，不写入登录态。
- `POST /logout` 只清除本应用会话并 `303` 回 `/`，不跳转学校 CAS logout。
- 会话 Cookie 设为 `HttpOnly` + `SameSite=Lax`；`Secure` 由环境变量控制。
- CAS `serviceValidate` 使用显式 `HTTPS_PROXY`。
- 只解析 CAS `user`，不把未确认的属性当成姓名或邮箱。
