# Audio_Transcriber - one-line bootstrap (clone + install, keyless Option B).
#
# ONE instruction, from a normal (non-admin) PowerShell window:
#   irm https://raw.githubusercontent.com/tthompson0808/audio-transcriber/feat/teams-stereo-local/installer/bootstrap.ps1 | iex
#
# It clones (or updates) the repo to C:\src\audio-transcriber, then runs
# installer\install.ps1, which installs the keyless local transcriber, stages
# the speech model, and registers the always-on capture task. The installer
# asks only for the owner's first name and where to save transcripts.
#
# Written to be safe when piped to iex: no param() block, no $PSScriptRoot.

$ErrorActionPreference = "Stop"
$Branch  = "feat/teams-stereo-local"
$RepoUrl = "https://github.com/tthompson0808/audio-transcriber"
$Dest    = "C:\src\audio-transcriber"

Write-Host ""
Write-Host "Audio_Transcriber one-line setup" -ForegroundColor White
Write-Host "================================" -ForegroundColor White

# 1. git present?
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "git is not installed. Install Git for Windows from https://git-scm.com/download/win, then re-run this line." -ForegroundColor Red
    return
}

# 2. clone fresh, or reset an existing checkout to match the remote branch
if (Test-Path (Join-Path $Dest ".git")) {
    Write-Host "-> Updating existing checkout at $Dest" -ForegroundColor Cyan
    git -C $Dest fetch origin $Branch
    git -C $Dest checkout -B $Branch "origin/$Branch"
} else {
    Write-Host "-> Cloning $Branch to $Dest" -ForegroundColor Cyan
    New-Item -ItemType Directory -Path (Split-Path $Dest -Parent) -Force | Out-Null
    git clone -b $Branch $RepoUrl $Dest
}

# 3. run install.ps1 as a FILE (so its own param()/$PSScriptRoot resolve correctly)
$installer = Join-Path $Dest "installer\install.ps1"
if (-not (Test-Path $installer)) {
    Write-Host "Installer not found at $installer" -ForegroundColor Red
    return
}
Write-Host "-> Running installer (it will ask for the owner name and the save folder)" -ForegroundColor Cyan
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer -RepoPath $Dest
