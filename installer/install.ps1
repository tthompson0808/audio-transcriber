# Audio_Transcriber — Windows installer
# Run as the CEO's user (not admin), from PowerShell:
#   .\install.ps1
#
# What it does:
#   1. Verifies Python 3.12+ (offers to install if missing)
#   2. Creates a virtual env at $env:LOCALAPPDATA\Audio_Transcriber\venv
#   3. Installs the audio_transcriber package + dependencies
#   4. Creates OneDrive\Audio_Transcriber\{meetings,Drop_Recordings,Drop_Transcripts,logs}
#   5. Registers three scheduled tasks:
#        AudioTranscriber_AutoCapture  — at-logon, runs auto_capture_runner serve
#        AudioTranscriber_GraphPoll    — every 5 min, runs `audio_transcriber graph-poll`
#        AudioTranscriber_Updater      — daily 03:00, runs update_check.ps1
#   6. Places a desktop shortcut → http://127.0.0.1:8765/
#   7. Starts the dashboard + tray
#
# Idempotent — safe to re-run.

[CmdletBinding()]
param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\Audio_Transcriber",
    [string]$RepoPath = $PSScriptRoot | Split-Path -Parent,  # parent of installer/
    [switch]$SkipPython
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step($msg) { Write-Host "→ $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "Audio_Transcriber installer" -ForegroundColor White
Write-Host "============================" -ForegroundColor White
Write-Host ""

# --- 1. Python ---
Write-Step "Checking Python 3.12+"
$python = $null
foreach ($cand in @("py -3.12", "py -3", "python", "python3")) {
    try {
        $ver = & $cand.Split(" ")[0] $cand.Split(" ")[1..($cand.Split(" ").Length-1)] -c "import sys; print(sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver -match "\(3, (1[2-9]|[2-9]\d)") {
            $python = $cand
            break
        }
    } catch {}
}
if (-not $python) {
    if ($SkipPython) {
        throw "Python 3.12+ not found and -SkipPython was specified."
    }
    Write-Warn "Python 3.12+ not found. Download: https://www.python.org/downloads/"
    Write-Host "  After installing Python, re-run this script." -ForegroundColor Yellow
    exit 1
}
Write-Ok "Using $python"

# --- 2. Venv ---
$venv = Join-Path $InstallRoot "venv"
Write-Step "Creating virtual env at $venv"
if (-not (Test-Path $venv)) {
    & $python.Split(" ")[0] $python.Split(" ")[1..($python.Split(" ").Length-1)] -m venv $venv
}
$pyExe = Join-Path $venv "Scripts\python.exe"
$pipExe = Join-Path $venv "Scripts\pip.exe"
Write-Ok "Venv ready"

# --- 3. Install package ---
Write-Step "Installing audio_transcriber + deps"
& $pyExe -m pip install --upgrade pip --quiet
& $pipExe install --quiet `
    anthropic openai `
    fastapi uvicorn jinja2 python-multipart `
    msal httpx `
    psutil pygetwindow watchdog `
    keyring pyaudiowpatch `
    pystray pillow win10toast-click
& $pipExe install --quiet --no-deps -e "$RepoPath"
Write-Ok "Dependencies installed"

# --- 4. OneDrive folders ---
Write-Step "Creating OneDrive data folders"
$onedrive = $env:OneDriveCommercial
if (-not $onedrive) { $onedrive = $env:OneDrive }
if (-not $onedrive -or -not (Test-Path $onedrive)) {
    Write-Warn "OneDrive not detected — falling back to $env:USERPROFILE"
    $onedrive = $env:USERPROFILE
}
$dataRoot = Join-Path $onedrive "Audio_Transcriber"
foreach ($sub in @("meetings", "Drop_Recordings", "Drop_Transcripts", "logs")) {
    $p = Join-Path $dataRoot $sub
    New-Item -ItemType Directory -Path $p -Force | Out-Null
}
Write-Ok "Data root: $dataRoot"

# --- 5. Scheduled tasks ---
Write-Step "Registering scheduled tasks"

function Register-Or-Update-Task($name, $action, $trigger, $desc) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
    }
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Description $desc -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable) `
        -RunLevel Limited | Out-Null
}

$autoAction = New-ScheduledTaskAction -Execute $pyExe -Argument "-m audio_transcriber.auto_capture_runner serve"
$autoTrigger = New-ScheduledTaskTrigger -AtLogOn
Register-Or-Update-Task "AudioTranscriber_AutoCapture" $autoAction $autoTrigger "Auto-record running Zoom meetings via WASAPI"

$graphAction = New-ScheduledTaskAction -Execute $pyExe -Argument "-m audio_transcriber graph-poll --lookback 1"
$graphTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)
Register-Or-Update-Task "AudioTranscriber_GraphPoll" $graphAction $graphTrigger "Poll Microsoft Graph for new Teams transcripts"

$updaterScript = Join-Path $PSScriptRoot "update_check.ps1"
$updaterAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -File `"$updaterScript`""
$updaterTrigger = New-ScheduledTaskTrigger -Daily -At "03:00am"
Register-Or-Update-Task "AudioTranscriber_Updater" $updaterAction $updaterTrigger "Nightly self-update check"

$trayAction = New-ScheduledTaskAction -Execute $pyExe -Argument "-m audio_transcriber.tray"
$trayTrigger = New-ScheduledTaskTrigger -AtLogOn
Register-Or-Update-Task "AudioTranscriber_Tray" $trayAction $trayTrigger "System tray icon"

$dashAction = New-ScheduledTaskAction -Execute $pyExe -Argument "-m audio_transcriber.dashboard.app"
$dashTrigger = New-ScheduledTaskTrigger -AtLogOn
Register-Or-Update-Task "AudioTranscriber_Dashboard" $dashAction $dashTrigger "Localhost dashboard server"

Write-Ok "Tasks registered"

# --- 6. Desktop shortcut ---
Write-Step "Placing desktop shortcut"
$shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Audio_Transcriber.lnk"
$wshell = New-Object -ComObject WScript.Shell
$lnk = $wshell.CreateShortcut($shortcut)
$lnk.TargetPath = "msedge.exe"
$lnk.Arguments = "http://127.0.0.1:8765/"
$lnk.IconLocation = "msedge.exe,0"
$lnk.Description = "Audio_Transcriber dashboard"
$lnk.Save()
Write-Ok "Shortcut: $shortcut"

# --- 7. Start services now ---
Write-Step "Starting services"
Start-ScheduledTask -TaskName "AudioTranscriber_Dashboard"
Start-ScheduledTask -TaskName "AudioTranscriber_Tray"
Start-ScheduledTask -TaskName "AudioTranscriber_AutoCapture"
Start-Sleep -Seconds 3
Write-Ok "Services running"

Write-Host ""
Write-Host "Install complete." -ForegroundColor Green
Write-Host "Next: open http://127.0.0.1:8765/settings to enter API keys, then run:" -ForegroundColor White
Write-Host "  $pyExe -m audio_transcriber graph-auth --client-id <ID> --tenant-id <TENANT>" -ForegroundColor White
Write-Host ""
