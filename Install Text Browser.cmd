@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_once.ps1"
if errorlevel 1 (
    echo.
    echo Installation failed. See message above.
    pause
    exit /b 1
)
echo.
echo Installation ready. Double-click Text Browser Excel on the Desktop.
pause
