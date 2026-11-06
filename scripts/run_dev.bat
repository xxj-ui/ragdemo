@echo off
REM zhiwen 后端启动脚本（单 worker，02 S-01）
REM 用法：scripts\run_dev.bat
REM 注意：本文件必须保存为 GBK/ANSI 编码（cmd.exe 在中文 Windows 上按 GBK 读 .bat）；
REM       若用 UTF-8 保存，中文注释会被解析成命令并报「不是内部或外部命令」。
setlocal enabledelayedexpansion

cd /d "%~dp0.."

REM —— 非敏感默认值：MinIO 宿主端口 9100（容器内仍 9000，见 docker-compose.yml）——
if not defined RAG_STORAGE_BACKEND set "RAG_STORAGE_BACKEND=minio"
if not defined RAG_S3_ENDPOINT set "RAG_S3_ENDPOINT=http://127.0.0.1:9100"
if not defined RAG_S3_BUCKET set "RAG_S3_BUCKET=zhiwen"
if not defined RAG_S3_REGION set "RAG_S3_REGION=us-east-1"

REM —— 从 .env 读密钥/账号（.env 已被 .gitignore 排除，只在本进程生效）——
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if not "%%~A"=="" set "%%~A=%%~B"
    )
)

REM —— 用 MinIO 账号兜底 S3 凭据 ——
if not defined RAG_S3_ACCESS_KEY if defined MINIO_ROOT_USER set "RAG_S3_ACCESS_KEY=!MINIO_ROOT_USER!"
if not defined RAG_S3_SECRET_KEY if defined MINIO_ROOT_PASSWORD set "RAG_S3_SECRET_KEY=!MINIO_ROOT_PASSWORD!"

REM —— 用 .env 里的 PG 口令拼 DSN（沿用既有 54328）——
if not defined RAG_DB_DSN if defined POSTGRES_PASSWORD (
    set "RAG_DB_DSN=postgresql://!POSTGRES_USER!:!POSTGRES_PASSWORD!@127.0.0.1:54328/!POSTGRES_DB!"
)

echo [配置] RAG_STORAGE_BACKEND=%RAG_STORAGE_BACKEND%  RAG_S3_ENDPOINT=%RAG_S3_ENDPOINT%  RAG_S3_BUCKET=%RAG_S3_BUCKET%

if "%RAG_DB_DSN%"=="" (
    echo [错误] 未设置 RAG_DB_DSN。示例（不要把密码提交进版本库）：
    echo    set RAG_DB_DSN=postgresql://root:^<password^>@127.0.0.1:54328/zhiwen
    exit /b 1
)
if "%DEEPSEEK_API_KEY%"=="" (
    echo [警告] 未设置 DEEPSEEK_API_KEY，问答接口会返回 LLM_KEY_MISSING。
)
if "%RAG_STORAGE_BACKEND%"=="minio" if "%RAG_S3_SECRET_KEY%"=="" (
    echo [错误] RAG_STORAGE_BACKEND=minio 但 RAG_S3_SECRET_KEY 为空（.env 里也没有 MINIO_ROOT_PASSWORD）。
    exit /b 1
)

if not exist "server\app.py" (
    echo [未就绪] server\app.py 尚未实现（M1 交付物）。
    echo 当前可用 CLI 自检：python -m server.main --help
    exit /b 2
)

echo [启动] uvicorn server.app:app --host 127.0.0.1 --port 8000 --workers 1
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000 --workers 1 --reload
