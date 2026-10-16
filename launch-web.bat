@echo off
REM ---------------------------------------------------------------
REM  EliLain-Music - browser dashboard
REM    Usage: launch-web.bat [port]
REM ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PY="
if exist "%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe" (
    set "PY=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
) else (
    set "PY=python"
)

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8081"

echo EliLain-Music - web dashboard
echo   http://127.0.0.1:%PORT%
echo.
echo Press Ctrl+C to stop the server.
echo.
"%PY%" -m elilain_music.web --port %PORT%
if errorlevel 1 pause
endlocal