# 107 Workspace CAS 反向代理

本目录保存 `ustccas-revproxy` 的可审查适配：Nginx 入口、认证服务、上游补丁和运行说明。
不向第三方上游仓库推送。

当前联调拓扑（非 Docker）：

```text
浏览器 --SSH 隧道--> 127.0.0.1:8107 Nginx
                         ├── 公开 SPA / 静态资源
                         ├── GET /login、POST /logout → 认证服务 127.0.0.1:8108
                         └── /api/ auth_request → 后端 127.0.0.1:8000
```

隧道：

```bash
ssh -N -L 127.0.0.1:8107:127.0.0.1:8107 dfy2
```

## 行为契约

- 未登录浏览器可以加载公开 SPA 与静态资源。
- `/api/` 使用 Nginx [`auth_request`](https://nginx.org/en/docs/http/ngx_http_auth_request_module.html)。未认证返回 JSON `401`，不跳转 CAS。
- `/auth` 只从已验证会话返回 `X-User-ID`。姓名、邮箱未取得时不传，不推测 CAS 属性。
- Nginx 覆盖身份 Header，并清除客户端 `X-User`。
- `GET /login` 由代理发起认证并处理回调；成功后回到 `/`。前端只做整页导航。
- `POST /login/password` 校验本地管理员账密，成功后写入同一会话并注入 `X-User-Provider: local`。
- `POST /logout` 清除 107 会话 Cookie，随后 `303` 回到 `/`。不主动退出学校全局 SSO。
- 浏览器 origin 与 CAS service 使用固定配置，不根据不可信请求头生成回调。
- 登录回调保留随机会话 `id` 校验；失败时不给出登录态。
- 会话 Cookie：`HttpOnly`、`SameSite=Lax`。HTTP 隧道联调可关闭 `Secure`；HTTPS 入口必须开启。
- 退出和 API 写请求校验 `Origin` / `Referer`。敏感响应 `Cache-Control: no-store`。

## 启动

1. 复制 `env.example` 为 `env`，填入 `SECRET_KEY` 和已验证可用的 `HTTPS_PROXY`。
2. 构建前端到 `FRONTEND_DIST`。
3. 后端监听 `127.0.0.1:8000`，`WORKSPACE107_AUTH_MODE=ustc`。
4. `scripts/run-auth.sh`
5. `scripts/run-nginx.sh`（`NGINX_BIN` 可指向用户空间 Nginx）

Nginx 只监听 `127.0.0.1:8107`，不要启用发行版默认对外站点。

当前 dfy2 没有系统 Nginx。可把 Ubuntu `nginx` 软件包解压到用户目录，避免启用默认站点：

```bash
mkdir -p "$HOME/opt/nginx" /tmp/nginx-debs
cd /tmp/nginx-debs
apt-get download nginx nginx-common nginx-core
dpkg-deb -x nginx_*.deb "$HOME/opt/nginx"
dpkg-deb -x nginx-common_*.deb "$HOME/opt/nginx"
export NGINX_BIN="$HOME/opt/nginx/usr/sbin/nginx"
"$NGINX_BIN" -V 2>&1 | grep http_auth_request_module
```

## 应用到现有 checkout

服务器上的 `/home/zxbq/ustccas-revproxy` 保持为上游克隆。将本目录的
`auth/auth_server.py` 复制到该 checkout 的 `auth/auth_server.py` 即可运行；
Nginx 使用本目录模板，而不是上游 `nginx-site.conf`。补丁见 `patches/`。

## CAS 回环回调

CAS service 固定为 `${PUBLIC_ORIGIN}/login?id=...`。2026-09-05 对
`http://127.0.0.1:8107/login` 的探测结果见
[`CAS-LOOPBACK-PROBE.md`](CAS-LOOPBACK-PROBE.md)：IdP 返回错误码 `1510051`
「应用未对接认证服务」。等待受认可的 HTTPS 回调入口后再做真实闭环验收。
第三方 HTTP 回跳页不是可交付链路。

## 测试

模拟认证只存在于测试中：

```bash
PYTHONPATH=deploy/cas-revproxy uv run --with flask pytest -q deploy/cas-revproxy/tests
```

## 回滚

停止 8107 / 8108 进程，恢复演示后端原启动方式、版本和配置。不要删除数据库。
