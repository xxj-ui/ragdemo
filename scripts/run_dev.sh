#!/usr/bin/env bash
# ragdemo 后端启动脚本（单 worker，02 S-01）
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${RAG_DB_DSN:-}" ]; then
  echo "[错误] 未设置 RAG_DB_DSN。示例（不要把密码提交进版本库）："
  echo "  export RAG_DB_DSN='postgresql://root:<password>@127.0.0.1:54328/ragdemo'"
  exit 1
fi
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "[警告] 未设置 DEEPSEEK_API_KEY，问答接口会返回 LLM_KEY_MISSING。"
fi

if [ ! -f server/app.py ]; then
  echo "[未就绪] server/app.py 尚未实现（M1 交付物）。"
  echo "当前可用 CLI 自检：python -m server.main --help"
  exit 2
fi

echo "[启动] uvicorn server.app:app --host 127.0.0.1 --port 8000 --workers 1"
exec python -m uvicorn server.app:app --host 127.0.0.1 --port 8000 --workers 1 --reload
