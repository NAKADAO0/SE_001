@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ====================================================
echo   CodeMate-Agent - 一键启动多 Agent 系统服务 (基于 LangChain)
echo   参考 ruanfu_sheng 工业级微服务架构编排
echo ====================================================
echo.

:: ---- 0. 解释器与凭证检查 ----
set "PY_EXE=python"
if exist "E:\my_python\python.exe" (
    set "PY_EXE=E:\my_python\python.exe"
    echo [环境] 使用指定 Python 解释器: E:\my_python\python.exe
) else (
    echo [环境] 使用系统默认 Python 解释器: %PY_EXE%
)

if not exist ".env" (
    echo [警告] 未检测到根目录 .env 文件，正从 .env.example 自动创建...
    copy .env.example .env >nul
)

:: ---- 1. 端口清理 (8000 & 8501) ----
echo [1/3] 清理 8000 (FastAPI) 与 8501 (Streamlit) 旧进程...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 " 2^>nul') do (
    echo   [KILL] FastAPI - PID %%P on port 8000
    taskkill /PID %%P /F >nul 2>&1
)
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8501 " 2^>nul') do (
    echo   [KILL] Streamlit - PID %%P on port 8501
    taskkill /PID %%P /F >nul 2>&1
)
echo   清理完成。
echo.

:: ---- 2. 启动 FastAPI 后端服务 (Port 8000) ----
echo [2/3] 启动 FastAPI RESTful 后端微服务 (Port 8000)...
start "CodeMate-FastAPI-8000" /D "%~dp0" cmd /k ""%PY_EXE%" -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload"

:: 稍候 2 秒等待后端端口初始化
timeout /t 2 /nobreak >nul

:: ---- 3. 启动 Streamlit 前端交互工作台 (Port 8501) ----
echo [3/3] 启动 Streamlit 可视化交互工作台 (Port 8501)...
start "CodeMate-Streamlit-8501" /D "%~dp0" cmd /k ""%PY_EXE%" -m streamlit run web_app.py --server.port 8501"

echo.
echo ====================================================
echo   服务已全部就绪！
echo   - Web 工作台:  http://localhost:8501
echo   - 后端 Swagger: http://localhost:8000/docs
echo   - 停止全部服务请运行: kill_all.bat
echo ====================================================
echo.
pause
