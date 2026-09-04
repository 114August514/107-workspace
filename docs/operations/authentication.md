# 身份认证接入

107 Workspace 只把外部认证结果映射为内部 `User`。CAS 回答“这个人是谁”，
Workspace、Project、Run 等业务权限仍只依赖内部 `User`、Ownership 与 Membership。

## 运行模式

`WORKSPACE107_AUTH_MODE` 支持：

- `dev`：仅用于本地开发和受信任演示。读取 `X-User`，缺省为 `student`，并按用户名创建
  开发用户。
- `ustc`：读取受信任反向代理注入的 USTC CAS 身份。没有有效身份时返回 `401`。

本地模拟登录：

```bash
WORKSPACE107_AUTH_MODE=dev uv run uvicorn workspace107.main:create_app --factory
curl -H 'X-User: alice' http://127.0.0.1:8000/api/v1/me
```

## revproxy 与 Backend 的字段约定

`ustc` 模式使用以下请求头：

| Header | 必填 | 含义 |
| :--- | :---: | :--- |
| `X-User-ID` | 是 | CAS 中稳定且唯一的用户标识，保存为 `provider_user_id` |
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

当前仓库不包含 `ustccas-revproxy` 的部署配置，也无法在应用内区分“代理注入”与“客户端
伪造”的同名 Header。真实上线前必须在目标部署中完成 Header 清洗、网络隔离和端到端
验收；仅把 `WORKSPACE107_AUTH_MODE` 改为 `ustc` 不构成安全接入。
