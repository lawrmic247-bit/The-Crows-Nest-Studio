# Run from this directory using PowerShell after installing Python 3.11+ and FFmpeg.
$ErrorActionPreference = 'Stop'
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install Pillow piper-tts==1.8.0
New-Item -ItemType Directory -Force voices | Out-Null
& .\.venv\Scripts\python.exe -m piper.download_voices --data-dir voices en_US-lessac-medium
& .\.venv\Scripts\python.exe studio.py doctor
Write-Host "Ready. Run: .\.venv\Scripts\python.exe studio.py render episodes\01_lookout_intro.json --format short"
