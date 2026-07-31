@echo off
setlocal
title CampusMate AI - Vue Web

cd /d "%~dp0"

where node.exe >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js was not found in PATH.
    echo Install Node.js from https://nodejs.org/ and try again.
    goto :failed
)

where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm was not found in PATH.
    echo Repair the Node.js installation and try again.
    goto :failed
)

if not exist "package.json" (
    echo [ERROR] package.json was not found in:
    echo %CD%
    goto :failed
)

if not exist "node_modules\.bin\vite.cmd" (
    echo [INFO] Installing web dependencies. This may take a while...
    call npm.cmd install
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed.
        goto :failed
    )
)

echo ========================================
echo  CampusMate AI - Vue Web
echo  URL: http://127.0.0.1:5173
echo ========================================
echo.
echo Keep this window open. Press Ctrl+C to stop the server.
echo.

call npm.cmd run dev
if errorlevel 1 (
    echo.
    echo [ERROR] The web server exited with an error.
    goto :failed
)

echo.
echo The web server has stopped.
pause
exit /b 0

:failed
echo.
echo Press any key to close this window.
pause >nul
exit /b 1
