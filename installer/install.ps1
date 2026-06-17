# Audio_Transcriber - Windows installer (Option B: keyless, local, stereo + AEC)
#
# Run as the laptop owner (not admin), from the repo root in PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\installer\install.ps1
#
# What it does - no API keys, nothing cloud:
#   1. Verifies Python 3.12+
#   2. Creates a virtual env at <repo>\.venv
#   3. Installs the package + the Windows capture deps (keyless)
#   4. Stages the on-device speech model (small.en) for offline use
#   5. Points the app at the model and labels the owner's mic channel
#   6. Asks where transcripts should be saved
#   7. Registers the always-on auto-capture task (runs at every logon)
#
# Idempotent - safe to re-run.
[CmdletBinding()]
param(
    [string]$RepoPath = (Split-Path -Parent $PSScriptRoot),  # parent of installer/
    [string]$OwnerName = "",
    [switch]$SkipPython
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step($msg) { Write-Host "-> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [ok] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "Audio_Transcriber installer (Option B: local, keyless)" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor White
Write-Host ""

# --- 1. Python ---
Write-Step "Checking Python 3.12+"
$python = $null
foreach ($cand in @("py -3.12", "py -3", "python", "python3")) {
    try {
        $parts = $cand.Split(" ")
        $ver = & $parts[0] $parts[1..($parts.Length-1)] -c "import sys; print(sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver -match "\(3, (1[2-9]|[2-9]\d)") { $python = $cand; break }
    } catch {
        Write-Verbose "Probe for '$cand' failed: $($_.Exception.Message)"
    }
}
if (-not $python) {
    if ($SkipPython) { throw "Python 3.12+ not found and -SkipPython was specified." }
    Write-Warn "Python 3.12+ not found. Install from https://www.python.org/downloads/ then re-run."
    exit 1
}
$pyParts = $python.Split(" ")
Write-Ok "Using $python"

# --- 2. Venv (repo-local, matches the manual runbook) ---
$venv = Join-Path $RepoPath ".venv"
Write-Step "Creating virtual env at $venv"
if (-not (Test-Path $venv)) {
    & $pyParts[0] $pyParts[1..($pyParts.Length-1)] -m venv $venv
}
$pyExe = Join-Path $venv "Scripts\python.exe"
Write-Ok "Venv ready"

# --- 3. Install package + Windows capture deps (keyless) ---
Write-Step "Installing audio_transcriber + capture deps (no API keys)"
& $pyExe -m pip install --upgrade pip --quiet
& $pyExe -m pip install --quiet -e $RepoPath
& $pyExe -m pip install --quiet psutil pygetwindow watchdog pyaudiowpatch pystray pillow win10toast-click pycaw comtypes
Write-Ok "Dependencies installed"

# --- 4. Stage the on-device speech model (offline-friendly) ---
$modelDir = Join-Path (Split-Path -Parent $RepoPath) "at-model-small.en"
Write-Step "Staging speech model small.en (about 460 MB) -> $modelDir"
if (Test-Path (Join-Path $modelDir "model.bin")) {
    Write-Ok "Model already staged"
} else {
    & $pyExe -m audio_transcriber stage-model --model small.en --out $modelDir
}

# --- 5. Point the app at the model + label the owner's mic channel ---
if (-not $OwnerName) {
    $OwnerName = Read-Host "  Laptop owner's first name (labels their mic channel, e.g. Tyson)"
    if ([string]::IsNullOrWhiteSpace($OwnerName)) { $OwnerName = "Me" }
}
& $pyExe -m audio_transcriber set-config transcribe.model_dir $modelDir | Out-Null
& $pyExe -m audio_transcriber set-config capture.owner_name $OwnerName | Out-Null
Write-Ok "Model + owner ($OwnerName) configured"

# --- 6. Where transcripts are saved ---
Write-Step "Choosing where meeting transcripts are saved"
$onedrive = $env:OneDriveCommercial
if (-not $onedrive) { $onedrive = $env:OneDrive }
if (-not $onedrive -or -not (Test-Path $onedrive)) { $onedrive = $env:USERPROFILE }
$defaultData = Join-Path $onedrive "Audio_Transcriber"
$answer = Read-Host "  Save transcripts where? Press Enter for default`n  [$defaultData]"
if ([string]::IsNullOrWhiteSpace($answer)) { $dataRoot = $defaultData } else { $dataRoot = $answer.Trim('"').Trim() }
& $pyExe -m audio_transcriber set-config data_dir "$dataRoot" | Out-Null
Write-Ok "Transcripts will be saved to: $dataRoot"

# --- 7. Always-on auto-capture (logon task) ---
Write-Step "Registering the always-on auto-capture task"
& "$PSScriptRoot\register-autocapture.ps1" -RepoPath $RepoPath

Write-Host ""
Write-Host "Install complete. Transcription is ON and always at the ready." -ForegroundColor Green
Write-Host ""
Write-Host "Turn it off for a private call, then back on:" -ForegroundColor White
Write-Host "  .\.venv\Scripts\python -m audio_transcriber teams-auto pause" -ForegroundColor Gray
Write-Host "  .\.venv\Scripts\python -m audio_transcriber teams-auto resume" -ForegroundColor Gray
Write-Host ""
