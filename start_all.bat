@echo off
chcp 65001 >nul 2>&1
setlocal

title CampusMate AI - Start All Services

cd /d "%~dp0"

echo ============================================
echo   CampusMate AI - 一键启动全部服务
echo ============================================
echo.
echo   本脚本按依赖顺序拉起三个进程：
echo     openmaic-service (4010)  -^> FastAPI (8000) -^> Vite Web (5174)
echo.
echo   为什么需要它：只启动 Web 和后端时，OpenMAIC 融合链路会在每次
echo   请求上返回 503（页面提示"连不上受管 OpenMAIC 服务"），因为
echo   后端网关连不上没有启动的 openmaic-service。
echo.
echo   先体检（只读，不改配置）：
echo.

where node.exe >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 未找到 Node.js。请安装 Node.js 22.19 或更高版本后重试。
    goto :failed
)

node "scripts\openmaic-local.mjs" doctor
if errorlevel 1 (
    echo.
    echo [ERROR] 体检未通过，请先修复上面列出的阻塞项。
    goto :failed
)

echo.
echo   按 Ctrl+C 可同时停止三个进程。
echo.
node "scripts\openmaic-local.mjs" start

echo.
echo 服务已停止。
pause
exit /b 0

:failed
echo.
pause
exit /b 1
