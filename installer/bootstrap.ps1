# Audio_Transcriber - one-line bootstrap (clone + install, keyless Option B).
#
# ONE instruction, from a normal (non-admin) PowerShell window:
#   irm https://raw.githubusercontent.com/tthompson0808/audio-transcriber/main/installer/bootstrap.ps1 | iex
#
# It clones (or updates) the repo to C:\src\audio-transcriber, then runs
# installer\install.ps1, which installs the keyless local transcriber, stages
# the speech model, and registers the always-on capture task. The installer
# asks only for the owner's first name and where to save transcripts.
#
# Written to be safe when piped to iex: no param() block, no $PSScriptRoot.

$ErrorActionPreference = "Stop"
$Branch  = "main"
$RepoUrl = "https://github.com/tthompson0808/audio-transcriber"
$Dest    = "C:\src\audio-transcriber"

# Native (.exe) calls do NOT honor $ErrorActionPreference in Windows PowerShell 5.1.
# Run the command and throw on a non-zero exit so a failed clone/checkout/install stops here.
function Invoke-Native {
    $cmd = $args[0]
    $rest = if ($args.Length -gt 1) { $args[1..($args.Length - 1)] } else { @() }
    & $cmd @rest
    if ($LASTEXITCODE -ne 0) { throw "Command failed (exit $LASTEXITCODE): $($args -join ' ')" }
}

Write-Host ""
Write-Host "Audio_Transcriber one-line setup" -ForegroundColor White
Write-Host "================================" -ForegroundColor White

# 1. git present?
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "git is not installed. Install Git for Windows from https://git-scm.com/download/win, then re-run this line." -ForegroundColor Red
    return
}

# 2. clone fresh, update an existing checkout, or stop on a non-git folder
if (Test-Path (Join-Path $Dest ".git")) {
    Write-Host "-> Updating existing checkout at $Dest" -ForegroundColor Cyan
    Invoke-Native git -C $Dest fetch origin $Branch
    Invoke-Native git -C $Dest checkout -B $Branch "origin/$Branch"
} elseif (Test-Path $Dest) {
    Write-Host "$Dest exists but is not a git checkout. Move it aside or delete it, then re-run." -ForegroundColor Red
    return
} else {
    Write-Host "-> Cloning $Branch to $Dest" -ForegroundColor Cyan
    New-Item -ItemType Directory -Path (Split-Path $Dest -Parent) -Force | Out-Null
    Invoke-Native git clone -b $Branch $RepoUrl $Dest
}

# 3. run install.ps1 as a FILE (so its own param()/$PSScriptRoot resolve correctly)
$installer = Join-Path $Dest "installer\install.ps1"
if (-not (Test-Path $installer)) {
    Write-Host "Installer not found at $installer" -ForegroundColor Red
    return
}
Write-Host "-> Running installer (it will ask for the owner name and the save folder)" -ForegroundColor Cyan
Invoke-Native powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer -RepoPath $Dest
