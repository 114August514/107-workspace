# 107 Workspace 后端镜像
#
# 多阶段构建：构建阶段用 uv 装依赖，运行阶段只留虚拟环境和源码，
# 不带 uv、编译器和构建缓存。运行用户是非 root。
#
# 依赖层和源码层分开复制：改代码不会让依赖层缓存失效。

# ---------- 构建阶段 ----------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# 只装第三方依赖。--extra postgres 带上 asyncpg，容器里连的是 PostgreSQL。
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra postgres --no-install-project

# 再装项目本身
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra postgres

# ---------- 运行阶段 ----------
FROM python:3.12-slim-bookworm AS runtime
ARG WORKSPACE107_SERVICE_UID=10001
ARG WORKSPACE107_SERVICE_GID=10001

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    WORKSPACE107_STORAGE_ROOT=/var/lib/workspace107/storage

RUN apt-get update \
 && apt-get install --yes --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

# Defaults are local-container identities only. Real deployments must rebuild with the
# human-validated service UID/GID and separately validate compute/shared-GID access.
RUN groupadd --gid "${WORKSPACE107_SERVICE_GID}" workspace \
 && useradd --uid "${WORKSPACE107_SERVICE_UID}" --gid "${WORKSPACE107_SERVICE_GID}" \
      --create-home --shell /usr/sbin/nologin workspace

WORKDIR /app

# 虚拟环境里的项目是可编辑安装，指向 /app/src，所以路径必须和构建阶段一致。
COPY --from=builder --chown=workspace:workspace /app/.venv /app/.venv
COPY --chown=workspace:workspace src ./src
COPY --chown=workspace:workspace migrations ./migrations
COPY --chown=workspace:workspace alembic.ini docker-entrypoint.sh ./

RUN chmod +x docker-entrypoint.sh \
 && mkdir -p "$WORKSPACE107_STORAGE_ROOT" \
 && chown -R workspace:workspace "$WORKSPACE107_STORAGE_ROOT" \
 && chmod 0750 "$WORKSPACE107_STORAGE_ROOT"

USER workspace
EXPOSE 8000

# 用 /ready 而不是 /health：compose 靠这个健康状态决定什么时候放前端进来，
# 数据库还没通就接流量只会让用户看到一堆 500。
# 不额外装 curl，用标准库探活即可。
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=6 \
  CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready', timeout=3).status == 200 else 1)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "workspace107.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
