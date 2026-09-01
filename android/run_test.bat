@echo off
setlocal
set SAFE_RM_ALLOWED_PATH=
set SAFE_RM_ENV_PATH=
set TOOLHOST_RUNTIME_MODE=
set "JAVA_HOME=%~dp0.tools\jdk21-full\jdk-21.0.12+8"
set "PATH=%JAVA_HOME%\bin;%PATH%"
if not exist "%JAVA_HOME%\bin\java.exe" (
  echo Bundled JDK 21 not found: %JAVA_HOME%
  exit /b 1
)
call "%~dp0gradlew.bat" test --tests "com.example.campusai.workers.ChaoxingSyncWorkerTest"
exit /b %errorlevel%
