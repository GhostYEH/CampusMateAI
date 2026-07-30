@echo off
REM Linear script, no nested if-blocks, no menu.
REM All output ASCII to avoid cmd mis-parsing UTF-8 bytes.
title CampusMate AI - Web Frontend

cd /d "%~dp0"

REM ===== Check Flutter availability =====
where flutter >nul 2>nul
if errorlevel 1 (
    echo [ERROR] flutter command not found in PATH.
    echo Please install Flutter SDK and add its bin folder to system PATH.
    pause
    exit /b 1
)

REM ===== Ensure pub dependencies are installed =====
if not exist ".dart_tool\package_config.json" (
    echo [INFO] First run, fetching dependencies...
    call flutter pub get
    if errorlevel 1 (
        echo [ERROR] Failed to fetch dependencies. Check your network and retry.
        pause
        exit /b 1
    )
)

REM ===== Probe backend (non-blocking, informational only) =====
echo [CHECK] Verifying backend at http://localhost:8000 ...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:8000/api/v1/health' -TimeoutSec 3 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if errorlevel 1 goto backend_down
goto backend_up

:backend_down
echo [WARN] Backend not detected at http://localhost:8000
echo        Please run start_backend.bat in another window first.
echo        Frontend will still start, but backend features will be unavailable.
echo.
goto start_frontend

:backend_up
echo [OK]   Backend is running.
echo.

:start_frontend
echo ========================================
echo  CampusMate AI - Web Frontend
echo  Mode:    Real backend
echo  API:     http://localhost:8000
echo  Docs:    http://localhost:8000/docs
echo  Browser will open automatically.
echo  Close this window or press Ctrl+C to stop.
echo ========================================
echo.

call flutter run -d chrome --dart-define=USE_MOCK_BACKEND=false --dart-define=API_BASE_URL=http://localhost:8000

echo.
echo ========================================
echo  Frontend stopped.
echo ========================================
pause
