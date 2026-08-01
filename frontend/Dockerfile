# 107 Workspace 前端镜像
#
# 构建阶段产出静态资源，运行阶段用非 root 的 nginx 提供服务，
# 并把 /api 反代到后端——前后端同源，生产环境不需要 CORS。

# ---------- 构建阶段 ----------
FROM node:24-alpine AS builder

WORKDIR /app

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm run build

# ---------- 运行阶段 ----------
# nginx-unprivileged 以非 root 运行并监听 8080，不需要绑定特权端口的能力。
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

# alpine 自带 busybox wget，不用为探活再装一个包。
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD wget --quiet --spider http://127.0.0.1:8080/ || exit 1
