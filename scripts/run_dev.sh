#!/usr/bin/env bash
# ragdemo 后端启动脚本（单 worker，02 S-01）
# 配置优先级：已有环境变量 > 项目根 .env（docker compose 用，含密码且不入库）> 脚本内默认值
set -euo pipefail
cd "$(dirname "$0")/.."

# —— 非敏感默认值：MinIO 宿主端口 9100（容器内仍 9000，见 docker-compose.yml）——
: "${RAG_STORAGE_BACKEND:=minio}"
: "${RAG_S3_ENDPOINT:=http://127.0.0.1:9100}"
: "${RAG_S3_BUCKET:=ragdemo}"
: "${RAG_S3_REGION:=us-east-1}"

# —— 从 .env 读密钥/账号（只在本进程生效）——
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# —— 用 MinIO 账号兜底 S3 凭据 ——
: "${RAG_S3_ACCESS_KEY:=${MINIO_ROOT_USER:-}}"
: "${RAG_S3_SECRET_KEY:=${MINIO_ROOT_PASSWORD:-}}"

# —— 用 .env 里的 PG 口令拼 DSN（沿用既有 54328）——
if [ -z "${RAG_DB_DSN:-}" ] && [ -n "${POSTGRES_PASSWORD:-}" ]; then
  RAG_DB_DSN="postgresql://${POSTGRES_USER:-root}:${POSTGRES_PASSWORD}@127.0.0.1:54328/${POSTGRES_DB:-ragdemo}"
fi

export RAG_STORAGE_BACKEND RAG_S3_ENDPOINT RAG_S3_BUCKET RAG_S3_REGION
export RAG_S3_ACCESS_KEY RAG_S3_SECRET_KEY
export RAG_DB_DSN="${RAG_DB_DSN:-}"

echo "[配置] RAG_STORAGE_BACKEND=$RAG_STORAGE_BACKEND  RAG_S3_ENDPOINT=$RAG_S3_ENDPOINT  RAG_S3_BUCKET=$RAG_S3_BUCKET"

if [ -z "${RAG_DB_DSN:-}" ]; then
  echo "[错误] 未设置 RAG_DB_DSN，且 .env 里没有 POSTGRES_PASSWORD 可拼。示例（不要把密码提交进版本库）："
  echo "  export RAG_DB_DSN='postgresql://root:***@127.0.0.1:54328/ragdemo'"
  exit 1
fi
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "[警告] 未设置 DEEPSEEK_API_KEY，问答接口会返回 LLM_KEY_MISSING。"
fi
if [ "$RAG_STORAGE_BACKEND" = "minio" ] && [ -z "${RAG_S3_SECRET_KEY:-}" ]; then
  echo "[错误] RAG_STORAGE_BACKEND=minio 但 RAG_S3_SECRET_KEY 为空（.env 里也没有 MINIO_ROOT_PASSWORD）。"
  exit 1
fi

if [ ! -f server/app.py ]; then
  echo "[未就绪] server/app.py 尚未实现（M1 交付物）。"
  echo "当前可用 CLI 自检：python -m server.main --help"
  exit 2
fi

echo "[启动] uvicorn server.app:app --host 127.0.0.1 --port 8000 --workers 1"
exec python -m uvicorn server.app:app --host 127.0.0.1 --port 8000 --workers 1 --reload
