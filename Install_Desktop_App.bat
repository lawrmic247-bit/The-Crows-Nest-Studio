@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo THE CROWS NEST - DESKTOP APP INSTALLER
echo ==========================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install_Desktop_App.ps1"
if errorlevel 1 (
    echo.
    echo Installation did not complete. See the error above.
    pause
    exit /b 1
)
echo.
echo Desktop shortcut created. Double-click it to open the video editor.
pause
