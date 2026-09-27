FROM node:22.14.0-bookworm-slim AS web-build
WORKDIR /build/web
RUN npm install --global pnpm@10.33.2
COPY web/ ./
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @wyckoff/web exec tsc --noEmit && pnpm --filter @wyckoff/web exec vite build --config vite.selfhost.config.ts

FROM python:3.11.11-slim-bookworm AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.11.11 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" HOME=/data SELFHOST_DATA_DIR=/data \
    SELFHOST_STATIC_DIR=/app/web/apps/web/dist-selfhost
WORKDIR /app
COPY . .
RUN uv sync --frozen --extra selfhost --no-editable --no-cache \
    && groupadd --gid 10001 wyckoff && useradd --uid 10001 --gid 10001 --home-dir /data wyckoff \
    && mkdir -p /data && chown 10001:10001 /data
COPY --from=web-build /build/web/apps/web/dist-selfhost ./web/apps/web/dist-selfhost
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["uvicorn", "selfhost.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-proxy-headers"]
