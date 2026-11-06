@echo off
REM zhiwen 前端启动脚本（M3 交付物；web/ 尚未创建）
setlocal
cd /d "%~dp0.."

if not exist "web\package.json" (
    echo [未就绪] web\ 尚未创建（M3 交付物：React + Vite + TS）。
    exit /b 2
)

cd web
if not exist node_modules (
    echo [安装] npm install
    call npm install
)
echo [启动] vite dev server（代理 /api ^-^> 127.0.0.1:8000，见 04 Q6）
call npm run dev
