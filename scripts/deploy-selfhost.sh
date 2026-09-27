#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo '请先安装并启动 Docker Engine/Desktop 和 Docker Compose v2.24+。' >&2
  exit 1
fi
if [ ! -f .env.selfhost ]; then
  cp .env.selfhost.example .env.selfhost
  chmod 600 .env.selfhost
fi
docker compose up --build -d --wait --wait-timeout 180
echo "已启动：http://${BIND_ADDRESS:-127.0.0.1}:${WEB_PORT:-8000}"
echo '首次登录口令：docker compose exec wyckoff cat /data/access-token'
echo '若设置了 WEB_TOKEN，请使用自定义口令。模型配置：编辑 .env.selfhost 后执行 docker compose up -d。'
