# 身份认证接入

107 Workspace 只把外部认证结果映射为内部 `User`。CAS 回答“这个人是谁”，
Workspace、Project、Run 等业务权限仍只依赖内部 `User`、Ownership 与 Membership。

## 运行模式

`WORKSPACE107_AUTH_MODE` 支持：

- `dev`：仅用于本地开发和受信任演示。读取 `X-User`，缺省为 `student`，并按用户名创建
  开发用户。
- `ustc`（默认）：读取受信任反向代理注入的身份。没有有效身份时返回 `401`。
  默认 `provider=ustc-cas`；代理在本地密码登录成功后注入 `X-User-Provider: local`。

本地模拟登录：

```bash
WORKSPACE107_AUTH_MODE=dev uv run uvicorn workspace107.main:create_app --factory
curl -H 'X-User: alice' http://127.0.0.1:8000/api/v1/me
```

`make dev` 读取仓库根目录 `.env` 和 `backend/.env`，默认使用 `ustc` 登录模式；缺少会话密钥时明确报错。
`WORKSPACE107_AUTH_MODE=ustc` 时会
同时启动认证服务，Vite 对 `/login`、`/login/password`、`/logout` 和 `/api/` 做与 Nginx
`auth_request` 相同的分流，浏览器打开 <http://127.0.0.1:5174> 就是公开登录页。
账密、会话密钥、CAS 代理都使用 `.env.example` 里的 `WORKSPACE107_*` 字段。
Vite 会把浏览器页面导航统一到 `WORKSPACE107_PUBLIC_ORIGIN` 配置的地址，避免混用
`localhost` 与 `127.0.0.1` 导致登录、退出的同源校验失败。退出请求仍须通过同源校验。

`WORKSPACE107_AUTH_MODE=dev` 时仍直接以 `student` 进入。Compose 默认 `web` 容器没有这些
路由，应保持 `AUTH_MODE=dev`。独立 Nginx 入口见
[`deploy/cas-revproxy/`](../../deploy/cas-revproxy/README.md)。

## revproxy 与 Backend 的字段约定

`ustc` 模式使用以下请求头：

| Header | 必填 | 含义 |
| :--- | :---: | :--- |
| `X-User-ID` | 是 | 稳定且唯一的用户标识，保存为 `provider_user_id` |
| `X-User-Provider` | 否 | `ustc-cas`（缺省）或 `local`（账密管理员） |
| `X-User-Name` | 否 | 首次创建内部 User 时使用的显示名；缺省为 `X-User-ID` |
| `X-User-Email` | 否 | 首次创建内部 User 时保存的邮箱 |

后端将 `provider=ustc-cas` 与 `X-User-ID` 组成外部身份唯一键。首次请求创建 `User` 和
`ExternalIdentity`；后续请求只按映射返回原 User，不按用户名合并，也不在登录时创建
Personal Workspace 或同步业务权限。显示名与邮箱目前只在首次创建时写入，不做目录同步。

## 必须满足的信任边界

HTTP Header 本身不能证明请求经过 CAS。真实部署必须同时满足：

1. revproxy 在转发前删除客户端提供的上述三个身份 Header；
2. revproxy 只用成功通过 USTC CAS 校验的服务端结果重新设置 Header；
3. Backend 端口只对 revproxy 所在受信任网络开放，外部请求不能绕过代理直连；
4. 面向用户的入口使用 HTTPS，并由 revproxy 管理 CAS 会话。

可审查的代理配置、上游补丁和运行说明保存在
[`deploy/cas-revproxy/`](../../deploy/cas-revproxy/README.md)。后端仍然无法自行区分
“代理注入”与“客户端伪造”的同名 Header。真实上线前必须由反向代理清洗 Header、
把 Backend 端口限制在受信任网络，并完成端到端验收；仅把 `WORKSPACE107_AUTH_MODE`
改为 `ustc` 不构成安全接入。

前端通过 `GET /api/v1/me` 确认当前用户。未登录显示公开首页；`GET /login`、
`POST /login/password` 与 `POST /logout` 由代理处理，前端只做整页跳转和同源表单提交。

本地管理员账密只用于受信任演示：登录后映射为 `provider=local` 的内部 User，并通过
「平台资产」User Group 的普通 Membership 管理平台 Environment / Shared Resource。
这不是设计文档 2.12 的 Platform Admin 控制台，也不授予业务数据特权。密码不得提交到仓库。

### 多账号本地演示

保留既有 `WORKSPACE107_LOCAL_ADMIN_*` 账号配置。额外本地账号通过
`WORKSPACE107_LOCAL_ACCOUNTS_JSON` 配置 JSON 数组，每项必须包含 `username`、
`display_name`、`password_hash` 三个字段。密码哈希使用 Werkzeug 的
`generate_password_hash` 生成；该配置只保存在忽略提交的 `.env` 中，默认空数组不会启用额外账号。
用户名由 1–64 位 ASCII 字母、数字、下划线、点、@ 或连字符组成，且不能与已有本地账号重复。
配置错误会阻止认证服务启动，报错不包含凭据内容。更改配置后重启 `make dev`。

额外账号与现有本地账号一样使用密码登录，身份为 `provider=local`，按各自用户名映射为独立 User。
登录不会自动加入 User Group、获得算力权益或管理员权限，组内协作仍需邀请并接受。
演示时使用两个浏览器或两个独立浏览器配置；同一浏览器的普通标签页共享会话。
一个账号退出登录不影响另一独立会话。
