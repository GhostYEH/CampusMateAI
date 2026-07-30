@echo off
chcp 65001 >nul
title CampusMate AI Backend

cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境 .venv
    echo 请先运行:python -m venv .venv  ^&^&  .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo ========================================
echo  CampusMate AI Backend
echo  监听: http://0.0.0.0:8000
echo  文档: http://localhost:8000/docs
echo  健康: http://localhost:8000/api/v1/health
echo ========================================
echo.
echo [提示] 此窗口必须保持打开,关闭即停止后端
echo [提示] 按 Ctrl+C 可停止服务
echo.

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo ========================================
echo  后端已停止
echo ========================================
pause
