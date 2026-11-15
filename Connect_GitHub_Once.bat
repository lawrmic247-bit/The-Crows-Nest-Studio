@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo THE CROWS NEST - ONE-TIME GITHUB SETUP
echo ===============================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Connect_GitHub_Once.ps1"
if errorlevel 1 echo Check the error above. No further automatic steps will run.
echo.
pause
