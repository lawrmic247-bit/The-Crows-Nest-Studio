@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  ".venv\Scripts\pythonw.exe" gui.py
) else (
  echo First-time setup required. Read README.md or run setup_windows.ps1 in PowerShell.
  py -3 gui.py
  pause
)
