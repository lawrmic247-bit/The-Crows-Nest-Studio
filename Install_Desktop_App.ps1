# The Crow's Nest Studio - Windows desktop installation, no administrator elevation required.
# Run through Install_Desktop_App.bat after extracting the complete ZIP.
param([switch]$SkipVoice, [switch]$SkipExe)
$ErrorActionPreference = 'Stop'
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$Install = Join-Path $env:LOCALAPPDATA 'Programs\TheCrowsNestStudio'
$Install = [IO.Path]::GetFullPath($Install)
$VenvPython = Join-Path $Install '.venv\Scripts\python.exe'
$VenvPythonW = Join-Path $Install '.venv\Scripts\pythonw.exe'
$ExePath = Join-Path $Install 'CrowsNestStudio.exe'

function Say([string]$msg) { Write-Host "[The Crows Nest] $msg" -ForegroundColor Cyan }
function Run([string]$exe,[string[]]$params) {
    & $exe @params
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $exe $($params -join ' ')" }
}
function Shortcuts {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $start = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
    $icon = Join-Path $Install 'assets\branding\CrowsNestStudio.ico'
    $shell = New-Object -ComObject WScript.Shell
    foreach ($destination in @((Join-Path $desktop 'The Crows Nest Studio.lnk'),(Join-Path $start 'The Crows Nest Studio.lnk'))) {
        $shortcut = $shell.CreateShortcut($destination)
        if (Test-Path $ExePath) {
            $shortcut.TargetPath = $ExePath
            $shortcut.Arguments = ''
        } else {
            $shortcut.TargetPath = $VenvPythonW
            $shortcut.Arguments = '"' + (Join-Path $Install 'gui.py') + '"'
        }
        $shortcut.WorkingDirectory = $Install
        $shortcut.IconLocation = "$icon,0"
        $shortcut.Description = 'The Crows Nest - independent documentary production studio'
        $shortcut.Save()
    }
}

try {
    Say "Installing desktop app to $Install"
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Say 'Windows Package Manager (winget) is unavailable. Install Python 3.12 manually from python.org then rerun.'
        throw 'winget is required for automatic Python installation.'
    }
    # Add existing FFmpeg install to this process PATH if it was installed through winget.
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
        $packages = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
        $ff = Get-ChildItem $packages -Filter ffmpeg.exe -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($ff) { $env:Path = "$($ff.DirectoryName);$env:Path" }
    }
    if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { throw 'FFmpeg not found. Install Gyan.FFmpeg with winget first.' }
    if (-not (Get-Command ffprobe -ErrorAction SilentlyContinue)) { throw 'FFprobe not found. Check the FFmpeg installation.' }

    # Python 3.14 can be retained. Use 3.12 in a separate private environment for TTS compatibility.
    $Python312 = $null
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            & py -3.12 -c 'import sys; assert sys.version_info[:2] == (3,12)' 2>$null
            if ($LASTEXITCODE -eq 0) { $Python312 = 'py' }
        } catch { $Python312 = $null }
    }
    if (-not $Python312) {
        Say 'Installing Python 3.12 alongside your existing Python (3.14 stays installed).'
        Run 'winget' @('install','-e','--id','Python.Python.3.12','--source','winget','--accept-package-agreements','--accept-source-agreements')
        if (Get-Command py -ErrorAction SilentlyContinue) {
            try {
                & py -3.12 -c 'import sys; assert sys.version_info[:2] == (3,12)' 2>$null
                if ($LASTEXITCODE -eq 0) { $Python312 = 'py' }
            } catch { $Python312 = $null }
        }
    }
    # Fall back to the standard user-scope python.org installation directory.
    $PythonPath = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
    if (-not $Python312 -and -not (Test-Path $PythonPath)) {
        throw 'Python 3.12 was installed but not detected. Close PowerShell and rerun the installer.'
    }

    New-Item -ItemType Directory -Force -Path $Install | Out-Null
    foreach ($file in @('gui.py','studio.py','narration.py','desktop_launcher.py','draft_with_ollama.py','production_engine.py','production_ui.py','voice_profiles.py','voice_studio_ui.py','qwen_voice.py','STUDIO_3_0_GUIDE.md','STUDIO_4_0_GUIDE.md','README.md','README_DESKTOP.md','requirements.txt','Connect_GitHub_Once.ps1','Connect_GitHub_Once.bat','fact_checker.py','fact_checker_ui.py','diagnostics.py','update_engine.py','VERSION')) {
        Copy-Item (Join-Path $Source $file) (Join-Path $Install $file) -Force
    }
    # Preserve generated episodes, locally supplied footage, existing voices and exports on upgrades.
    foreach ($folder in @('assets','episodes','voices','exports')) {
        $srcFolder = Join-Path $Source $folder
        $dstFolder = Join-Path $Install $folder
        New-Item -ItemType Directory -Force -Path $dstFolder | Out-Null
        if (Test-Path $srcFolder) {
            Get-ChildItem -LiteralPath $srcFolder -File -Recurse | ForEach-Object {
                $rel = $_.FullName.Substring($srcFolder.Length).TrimStart('\')
                $target = Join-Path $dstFolder $rel
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
                if ($folder -eq 'assets' -and $rel -like 'branding\*') {
                    Copy-Item -LiteralPath $_.FullName -Destination $target -Force
                } elseif (-not (Test-Path $target)) {
                    Copy-Item -LiteralPath $_.FullName -Destination $target
                }
            }
        }
    }
    if (-not (Test-Path $VenvPython)) {
        Say 'Creating private Python 3.12 environment.'
        if ($Python312) { Run 'py' @('-3.12','-m','venv',(Join-Path $Install '.venv')) }
        else { Run $PythonPath @('-m','venv',(Join-Path $Install '.venv')) }
    }
    Say 'Installing editor dependencies.'
    Run $VenvPython @('-m','pip','install','--upgrade','pip')
    Run $VenvPython @('-m','pip','install','Pillow>=10.2')

    # The editor runs immediately; the larger speech model installs on first user request.
    # Keep existing Piper voices for compatibility rather than reinstalling them automatically.
    if (-not $SkipVoice) {
        Say 'Natural narrator available: choose Kokoro and click Install selected voice inside the app.'
        Say 'This is a one-time download (~350 MB), never a paid API charge.'
    }

    if (-not $SkipExe) {
        Say 'Building the Windows application launcher (.exe).'
        & $VenvPython -m pip install pyinstaller
        if ($LASTEXITCODE -eq 0) {
            $ico = Join-Path $Install 'assets\branding\CrowsNestStudio.ico'
            $dist = Join-Path $Install 'dist'
            $build = Join-Path $Install 'build'
            & $VenvPython -m PyInstaller --noconfirm --onefile --windowed --name CrowsNestStudio --icon $ico --distpath $dist --workpath $build --specpath $build (Join-Path $Install 'desktop_launcher.py')
            if ($LASTEXITCODE -eq 0 -and (Test-Path (Join-Path $dist 'CrowsNestStudio.exe'))) {
                Copy-Item (Join-Path $dist 'CrowsNestStudio.exe') $ExePath -Force
                Say 'Created CrowsNestStudio.exe'
            } else { Write-Warning 'EXE build unavailable; desktop shortcut will launch the same graphical app directly.' }
        } else { Write-Warning 'PyInstaller unavailable; desktop shortcut will launch the same graphical app directly.' }
    }

    Shortcuts
    Say 'Checking installation...'
    Run $VenvPython @((Join-Path $Install 'studio.py'),'doctor')
    Say "SUCCESS: Use the desktop shortcut 'The Crows Nest Studio'."
    Say "Videos will be saved in $Install\exports"
} catch {
    Write-Host "INSTALLATION ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
