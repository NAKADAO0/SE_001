@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ====================================================
echo   CodeMate-Agent - 一键停止全部后台微服务
echo ====================================================
echo.

echo 正在停止 8000 端口服务 (FastAPI 后端)...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 " 2^>nul') do (
    echo   [KILL] PID %%P
    taskkill /PID %%P /F >nul 2>&1
)

echo 正在停止 8501 端口服务 (Streamlit 工作台)...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8501 " 2^>nul') do (
    echo   [KILL] PID %%P
    taskkill /PID %%P /F >nul 2>&1
)

echo.
echo 所有相关服务已全部优雅停止！
pause
