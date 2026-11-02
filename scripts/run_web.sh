#!/usr/bin/env bash
# ragdemo 前端启动脚本（M3 交付物；web/ 尚未创建）
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f web/package.json ]; then
  echo "[未就绪] web/ 尚未创建（M3 交付物：React + Vite + TS）。"
  exit 2
fi

cd web
[ -d node_modules ] || { echo "[安装] npm install"; npm install; }
echo "[启动] vite dev server（代理 /api -> 127.0.0.1:8000，见 04 Q6）"
exec npm run dev
