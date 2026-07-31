@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

cd /d "%~dp0backend"

echo ============================================
echo   CampusMate AI Backend
echo ============================================

:: 1. check / copy .env
if not exist ".env" (
    echo [1/4] .env not found, copying from .env.example ...
    copy /y ".env.example" ".env" >nul
    echo        .env created. Edit backend\.env to configure LLM.
) else (
    echo [1/4] .env exists, skip
)

:: 2. activate venv
echo [2/4] Activating Python venv ...
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else (
    echo [ERROR] venv\Scripts\activate.bat not found!
    echo         Please run in backend\: python -m venv venv
    pause
    exit /b 1
)

:: 3. install deps (with China mirror fallback)
echo [3/4] Installing dependencies ...

:: try default PyPI first, fallback to Tsinghua mirror on timeout
pip install -r requirements.txt --default-timeout=60 2>&1
if errorlevel 1 (
    echo.
    echo        Default PyPI timeout, retrying with Tsinghua mirror ...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --default-timeout=60
    if errorlevel 1 (
        echo [WARNING] Dependency install failed, trying to continue anyway...
    )
)

:: 4. start uvicorn
echo [4/4] Starting FastAPI ...
echo.
echo    Backend : http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo    Health  : http://localhost:8000/
echo    Press Ctrl+C to stop
echo ============================================
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
