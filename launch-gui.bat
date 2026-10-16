@echo off
REM ---------------------------------------------------------------
REM  EliLain-Music - desktop app
REM ---------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PY="
REM Prefer the Hermes venv (has PySide6 + yt-dlp), fall back to PATH python.
if exist "%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe" (
    set "PY=%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"
) else (
    set "PY=python"
)

"%PY%" -m elilain_music.cli doctor
echo.
echo Launching the desktop app...
echo.
"%PY%" -m elilain_music.gui
if errorlevel 1 (
    echo.
    echo The app exited with an error. Run the command above to see why.
    pause
)
endlocal