# The Crow's Nest Studio - one-time GitHub repository/bootstrap utility.
# Authentication is handled by GitHub CLI in the user's browser. No tokens saved here.
# By default, user explicitly selects visibility before anything is uploaded.
param(
  [string]$RepoName = 'The-Crows-Nest-Studio',
  [ValidateSet('public','private','ask')][string]$Visibility = 'ask'
)
$ErrorActionPreference = 'Stop'
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
function Say([string]$message) { Write-Host "[Crow's Nest GitHub] $message" -ForegroundColor Cyan }
function RequireSuccess([string]$step) {
  if ($LASTEXITCODE -ne 0) { throw "$step failed (exit code $LASTEXITCODE)." }
}
try {
  Set-Location -LiteralPath $Source
  Say 'This links a source-code repository to the GitHub account you authorize.'
  Write-Host 'A PUBLIC repository exposes the GitHub owner name and source code to the world.' -ForegroundColor Yellow
  Write-Host 'Your private recordings, generated videos, model weights and projects are excluded.'
  Write-Host 'PRIVATE repositories are not supported by the current unauthenticated desktop auto-updater.' -ForegroundColor Yellow
  if ($Visibility -eq 'ask') {
    $reply = (Read-Host 'Repository visibility: type PUBLIC or PRIVATE').Trim().ToLowerInvariant()
    if ($reply -notin @('public','private')) { throw 'Nothing uploaded. Enter PUBLIC or PRIVATE explicitly.' }
    $Visibility = $reply
  }
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Git is missing. Install Git for Windows first: https://git-scm.com/' }
    Say 'Git is missing. Installing Git for Windows.'
    & winget install --id Git.Git --exact --source winget --accept-package-agreements --accept-source-agreements
    RequireSuccess 'Git installation'
    $gitCandidate = Join-Path $env:ProgramFiles 'Git\cmd\git.exe'
    if (Test-Path $gitCandidate) { $env:Path = (Split-Path $gitCandidate) + ';' + $env:Path }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git installed, but PATH has not updated. Reopen PowerShell and rerun.' }
  }
  if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Say 'GitHub CLI is missing. Installing GitHub CLI with Windows Package Manager.'
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Install GitHub CLI from https://cli.github.com/ first.' }
    & winget install --id GitHub.cli --exact --source winget --accept-package-agreements --accept-source-agreements
    RequireSuccess 'GitHub CLI installation'
    $ghCmd = (Get-Command gh -ErrorAction SilentlyContinue)
    if (-not $ghCmd) {
      $candidate = Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe'
      if (Test-Path $candidate) { $env:Path = (Split-Path $candidate) + ';' + $env:Path }
    }
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'Reopen PowerShell and rerun; GitHub CLI was installed but not yet found in PATH.' }
  }
  & gh auth status -h github.com 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Say 'Authorize GitHub in your browser. The studio will never receive your password or token.'
    & gh auth login --hostname github.com --web --git-protocol https
    RequireSuccess 'GitHub sign-in'
  }
  $owner = (& gh api user --jq '.login').Trim()
  RequireSuccess 'Identify GitHub owner'
  if ($owner -notmatch '^[A-Za-z0-9-]+$') { throw 'GitHub returned an unexpected account name.' }
  $slug = "$owner/$RepoName"
  Say "GitHub repository: $slug ($Visibility)"
  if ($Visibility -eq 'public') {
    Write-Host "PUBLIC GITHUB URL: https://github.com/$slug" -ForegroundColor Yellow
    $confirm = (Read-Host 'The account owner will be visible publicly. Type PUBLISH to confirm').Trim()
    if ($confirm -cne 'PUBLISH') { throw 'Cancelled; no repository created or pushed.' }
  } else {
    $confirm = (Read-Host 'Type PRIVATE to create/push a private repository').Trim()
    if ($confirm -cne 'PRIVATE') { throw 'Cancelled; no repository created or pushed.' }
  }
  if (-not (Test-Path (Join-Path $Source '.github\workflows\release.yml'))) { throw 'Release workflow is missing. Extract the complete Studio ZIP.' }
  if (-not (Test-Path (Join-Path $Source '.gitignore'))) { throw '.gitignore missing; refusing to upload potentially private files.' }
  if (-not (Test-Path (Join-Path $Source '.git'))) {
    & git init -b main
    RequireSuccess 'Git initialization'
  }
  & git add --all
  RequireSuccess 'Git staging'
  $staged = @(& git diff --cached --name-only)
  $forbidden = @($staged | Where-Object { $_ -match '(?i)(^|/)(exports|\.venv|voices|\.updates|production_queue|fact_checks)/|\.(mp4|wav|flac|mp3|onnx|env|pem|p12)$|(^|/)(\.env|settings\.json|id_rsa)$' })
  if ($forbidden.Count -gt 0) { & git reset | Out-Null; throw "Unsafe files detected in commit staging: $($forbidden -join ', ')" }
  & git diff --cached --quiet
  if ($LASTEXITCODE -ne 0) {
    & git -c user.name="$owner" -c user.email="$owner@users.noreply.github.com" commit -m 'Studio v4.0.0: prompt queue, verification, voice studio and auto-updater'
    RequireSuccess 'Initial code commit'
  }
  & gh repo view $slug --json name --jq '.name' 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    Say 'The repository already exists. Checking its remote before pushing.'
    $remote = (& git remote get-url origin 2>$null)
    if ($LASTEXITCODE -eq 0 -and $remote -notmatch ([regex]::Escape("github.com/$slug")+'(\.git)?$')) {
      throw "Existing origin points elsewhere: $remote. Refusing to overwrite or push to an unexpected repository."
    }
    if ($LASTEXITCODE -ne 0) { & git remote add origin "https://github.com/$slug.git"; RequireSuccess 'Add GitHub origin' }
    & git push -u origin main
    RequireSuccess 'Push source code'
  } else {
    & gh repo create $slug "--$Visibility" --source $Source --remote origin --push --description 'Independent unofficial military history video production desktop studio'
    RequireSuccess 'GitHub repository creation'
  }
  $version = (Get-Content (Join-Path $Source 'VERSION') -Raw).Trim()
  $tag = "v$version"
  & git tag --list $tag | Out-Null
  & git rev-parse -q --verify "refs/tags/$tag" *> $null
  if ($LASTEXITCODE -ne 0) { & git tag $tag; RequireSuccess 'Release tag creation' }
  & git push origin $tag
  RequireSuccess 'Publish release tag'
  Say "Source uploaded and release workflow triggered: https://github.com/$slug/actions"
  if ($Visibility -eq 'public') {
    $settings = Join-Path $env:LOCALAPPDATA 'TheCrowsNestStudio\settings.json'
    $parent = Split-Path -Parent $settings
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $obj = @{}
    if (Test-Path $settings) {
      try { $current = Get-Content -LiteralPath $settings -Raw | ConvertFrom-Json; $current.psobject.Properties | ForEach-Object { $obj[$_.Name] = $_.Value } } catch { }
    }
    $obj['release_repo'] = $slug
    $tmp = "$settings.tmp"
    # Windows PowerShell 5.1 writes a UTF-8 BOM by default; Python's JSON reader expects no BOM.
    $json = $obj | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($tmp, $json, (New-Object System.Text.UTF8Encoding($false)))
    Move-Item -LiteralPath $tmp -Destination $settings -Force
    Say 'The desktop app now knows its GitHub release source. Future releases will be checked on launch.'
  } else {
    Say 'The repository is PRIVATE; updates are not enabled until an authorized release-access method is configured.'
  }
  Write-Host "GitHub repo: https://github.com/$slug" -ForegroundColor Green
  Write-Host 'Next: Open the GitHub Actions tab, verify the release job passes, then restart the studio.' -ForegroundColor Green
} catch {
  Write-Host "REPOSITORY SETUP STOPPED: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
