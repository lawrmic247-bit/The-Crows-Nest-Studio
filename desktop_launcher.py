#!/usr/bin/env python3
"""Lightweight executable launcher; all processing stays in installed app folder."""
import os,subprocess,sys
from pathlib import Path

APP_DIR=(Path(sys.executable).resolve().parent if getattr(sys,'frozen',False)
         else Path(__file__).resolve().parent)
pythonw=APP_DIR/'.venv'/'Scripts'/'pythonw.exe'
gui=APP_DIR/'gui.py'

def alert(message):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,message,"The Crow's Nest Studio",0x10)
    except Exception:
        print(message,file=sys.stderr)

if not pythonw.exists() or not gui.exists():
    alert('The Crow\'s Nest Studio installation is incomplete. Run Install_Desktop_App.bat again.')
    sys.exit(1)

try:
    subprocess.Popen([str(pythonw),str(gui)],cwd=str(APP_DIR),
                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
except Exception as exc:
    alert('Unable to start the desktop editor: '+str(exc))
    sys.exit(1)
