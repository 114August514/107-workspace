# 身份认证接入

107 Workspace 只把外部认证结果映射为内部 `User`。CAS 回答“这个人是谁”，
Workspace、Project、Run 等业务权限仍只依赖内部 `User`、Ownership 与 Membership。

## 运行模式

`WORKSPACE107_AUTH_MODE` 支持：

- `dev`：仅用于本地开发和受信任演示。读取 `X-User`，缺省为 `student`，并按用户名创建
  开发用户。
- `ustc`：读取受信任反向代理注入的身份。没有有效身份时返回 `401`。
  默认 `provider=ustc-cas`；代理在本地密码登录成功后注入 `X-User-Provider: local`。

本地模拟登录：

```bash
WORKSPACE107_AUTH_MODE=dev uv run uvicorn workspace107.main:create_app --factory
curl -H 'X-User: alice' http://127.0.0.1:8000/api/v1/me
```

`make dev` 和 Compose 默认走这条 `dev` 模式，前端一打开就会拿到当前用户，因此看不到
公开登录页。要在浏览器里看到账密 / 统一身份认证入口，必须同时满足：

1. 后端 `WORKSPACE107_AUTH_MODE=ustc`（没有代理注入的身份时 `/api/v1/me` 返回 401）；
2. 用 [`deploy/cas-revproxy/`](../../deploy/cas-revproxy/README.md) 的 Nginx 做入口
   （`/login`、`POST /login/password`、`POST /logout` 和 `/api/` 的 `auth_request`）。

只改 `AUTH_MODE=ustc`、仍用 Vite `:5174` 或 Compose `web` 容器，登录按钮没有对应代理路由，
不能当成登录演示。

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
