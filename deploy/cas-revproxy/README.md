# 107 Workspace CAS 反向代理

本目录保存 `ustccas-revproxy` 的可审查适配：Nginx 入口、认证服务、上游补丁和运行说明。
不向第三方上游仓库推送。

## 和 README 默认启动的区别

根目录 `make dev` 在 `WORKSPACE107_AUTH_MODE=ustc` 时已经带公开登录页：Vite `:5174`
加上认证服务，配置全部来自仓库 `.env` / `backend/.env`。本目录是同一套认证服务的
Nginx 入口，给不能走 Vite 的联调使用。

Compose 默认 `web` 容器监听 `:8107`，只反代 `/api`，默认 `AUTH_MODE=dev`，没有登录页。
两套 `:8107` 不要同时占用。

当前联调拓扑（非 Docker）：

```text
浏览器 --SSH 隧道--> 127.0.0.1:8107 Nginx
                         ├── 公开 SPA / 静态资源
                         ├── GET /login、POST /login/password、POST /logout → 认证服务 127.0.0.1:8108
                         └── /api/ auth_request → 后端 127.0.0.1:8000
```

从其他机器看演示时再开隧道：

```bash
ssh -N -L 127.0.0.1:8107:127.0.0.1:8107 dfy2
```

本机直接访问 <http://127.0.0.1:8107/> 不需要隧道。

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

## 本机启动（公开登录页）

在仓库根目录操作。不要同时跑 `make dev`（占用 `:8000`）或 Compose 默认栈（占用 `:8107`）。
若 `:8000` 已被占用，把后端改到其他端口，并同步修改 `BACKEND_ORIGIN`。

1. 安装依赖、迁移、构建前端：

```bash
./scripts/platform/posix/bootstrap.sh
make migrate
make build
```

需要「平台资产」演示数据时再执行（会创建 `provider=local` 的 `platform-admin`，
并作为 `grp_platform_assets` 的 Owner）：

```bash
cd backend
WORKSPACE107_AUTH_MODE=ustc uv run python -m workspace107.tools.seed --demo
cd ..
```

2. 后端以 `ustc` 模式监听 `127.0.0.1:8000`。不要用 `make dev`：

```bash
cd backend
WORKSPACE107_AUTH_MODE=ustc uv run uvicorn workspace107.main:create_app --factory --host 127.0.0.1 --port 8000
```

3. 复制并编辑认证配置：

```bash
cp deploy/cas-revproxy/env.example deploy/cas-revproxy/env
```

至少填写：

- `SECRET_KEY`：随机值，不要提交
- `FRONTEND_DIST`：本仓库 `frontend/dist` 的绝对路径
- `BACKEND_ORIGIN`：与上一步后端地址一致，默认 `http://127.0.0.1:8000`
- `LOCAL_ADMIN_PASSWORD`：演示密码，不要提交；用户名默认 `platform-admin`
- `HTTPS_PROXY`：学校 CAS `serviceValidate` 需要可用的出站代理。只演示账密登录时可以留空

4. 启动认证服务和 Nginx（两个终端，或自行放到后台）：

```bash
# 若本机没有带 auth_request 的系统 nginx，按下一节解压用户空间 nginx 并 export NGINX_BIN
./deploy/cas-revproxy/scripts/run-auth.sh
./deploy/cas-revproxy/scripts/run-nginx.sh
```

5. 浏览器打开 <http://127.0.0.1:8107/>。

未登录会看到公开首页（账密 + 统一身份认证）。账密使用步骤 3 的
`LOCAL_ADMIN_USERNAME` / `LOCAL_ADMIN_PASSWORD`。统一身份认证还需要学校侧登记的
HTTPS 回调，回环地址目前不能完成真实 CAS 闭环。

Nginx 只监听 `127.0.0.1:8107`，不要启用发行版默认对外站点。

## 用户空间 Nginx

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
