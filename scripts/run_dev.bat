@echo off
REM ragdemo 后端启动脚本（单 worker，02 S-01）
REM 用法：scripts\run_dev.bat
setlocal

cd /d "%~dp0.."

if "%RAG_DB_DSN%"=="" (
    echo [错误] 未设置 RAG_DB_DSN。示例（不要把密码提交进版本库）：
    echo    set RAG_DB_DSN=postgresql://root:^<password^>@127.0.0.1:54328/ragdemo
    exit /b 1
)
if "%DEEPSEEK_API_KEY%"=="" (
    echo [警告] 未设置 DEEPSEEK_API_KEY，问答接口会返回 LLM_KEY_MISSING。
)

if not exist "server\app.py" (
    echo [未就绪] server\app.py 尚未实现（M1 交付物）。
    echo 当前可用 CLI 自检：python -m server.main --help
    exit /b 2
)

echo [启动] uvicorn server.app:app --host 127.0.0.1 --port 8000 --workers 1
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000 --workers 1 --reload
