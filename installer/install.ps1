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
    [string]$RepoPath = "",
    [string]$OwnerName = "",
    [switch]$SkipPython
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not $RepoPath) {
    # Resolve <repo> in the body (not the param default): $PSScriptRoot can be empty
    # in a param default depending on how the script was launched.
    $here = $PSScriptRoot
    if (-not $here -and $PSCommandPath) { $here = Split-Path -Parent $PSCommandPath }
    if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
    $RepoPath = Split-Path -Parent $here
}

function Write-Step($msg) { Write-Host "-> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [ok] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!] $msg" -ForegroundColor Yellow }

# Native (.exe) calls do NOT honor $ErrorActionPreference in Windows PowerShell 5.1,
# so a failed git/pip/python would otherwise continue and half-complete the install.
# Run the command and throw on a non-zero exit code.
function Invoke-Native {
    $cmd = $args[0]
    $rest = if ($args.Length -gt 1) { $args[1..($args.Length - 1)] } else { @() }
    & $cmd @rest
    if ($LASTEXITCODE -ne 0) { throw "Command failed (exit $LASTEXITCODE): $($args -join ' ')" }
}

Write-Host ""
Write-Host "Audio_Transcriber installer (Option B: local, keyless)" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor White
Write-Host ""

# --- 1. Python ---
Write-Step "Checking Python 3.12+"
$python = $null; $pyCmd = $null; $pyArgs = @()
foreach ($cand in @("py -3.12", "py -3", "python", "python3")) {
    $parts = $cand -split ' '
    $cmd = $parts[0]
    $cargs = @(); if ($parts.Length -gt 1) { $cargs = $parts[1..($parts.Length - 1)] }
    try {
        $ver = & $cmd @cargs -c "import sys; print(sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $ver -match "\(3, (1[2-9]|[2-9]\d)") {
            $python = $cand; $pyCmd = $cmd; $pyArgs = $cargs; break
        }
    } catch {
        Write-Verbose "Probe for '$cand' failed: $($_.Exception.Message)"
    }
}
if (-not $python) {
    if ($SkipPython) { throw "Python 3.12+ not found and -SkipPython was specified." }
    Write-Warn "Python 3.12+ not found. Install from https://www.python.org/downloads/ then re-run."
    exit 1
}
Write-Ok "Using $python"

# --- 2. Venv (repo-local, matches the manual runbook) ---
$venv = Join-Path $RepoPath ".venv"
Write-Step "Creating virtual env at $venv"
if (-not (Test-Path $venv)) {
    Invoke-Native $pyCmd @pyArgs -m venv $venv
}
$pyExe = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $pyExe)) { throw "venv python not found at $pyExe (venv creation failed)." }
Write-Ok "Venv ready"

# --- 3. Install package + Windows capture deps (keyless) ---
Write-Step "Installing audio_transcriber + capture deps (no API keys)"
Invoke-Native $pyExe -m pip install --upgrade pip --quiet
Invoke-Native $pyExe -m pip install --quiet -e $RepoPath
Invoke-Native $pyExe -m pip install --quiet psutil pygetwindow watchdog pyaudiowpatch pystray pillow win10toast-click pycaw comtypes
Write-Ok "Dependencies installed"

# --- 4. Stage the on-device speech model (snapshot_download is cache-aware, so
#        re-running is cheap and also repairs a partially-staged model) ---
$modelDir = Join-Path (Split-Path -Parent $RepoPath) "at-model-small.en"
Write-Step "Staging speech model small.en (about 460 MB) -> $modelDir"
Invoke-Native $pyExe -m audio_transcriber stage-model --model small.en --out $modelDir
Write-Ok "Model staged"

# --- 5. Point the app at the model + label the owner's mic channel ---
if (-not $OwnerName) {
    $OwnerName = Read-Host "  Laptop owner's first name (labels their mic channel, e.g. Tyson)"
    if ([string]::IsNullOrWhiteSpace($OwnerName)) { $OwnerName = "Me" }
}
Invoke-Native $pyExe -m audio_transcriber set-config transcribe.model_dir $modelDir
Invoke-Native $pyExe -m audio_transcriber set-config capture.owner_name $OwnerName
Write-Ok "Model + owner ($OwnerName) configured"

# --- 6. Where transcripts are saved ---
Write-Step "Choosing where meeting transcripts are saved"
$onedrive = $env:OneDriveCommercial
if (-not $onedrive) { $onedrive = $env:OneDrive }
if (-not $onedrive -or -not (Test-Path $onedrive)) { $onedrive = $env:USERPROFILE }
$defaultData = Join-Path $onedrive "Audio_Transcriber"
$answer = Read-Host "  Save transcripts where? Press Enter for default`n  [$defaultData]"
if ([string]::IsNullOrWhiteSpace($answer)) { $dataRoot = $defaultData } else { $dataRoot = $answer.Trim('"').Trim() }
# $dataRoot is passed as a single argument (array element), so spaces are safe.
Invoke-Native $pyExe -m audio_transcriber set-config data_dir $dataRoot
Write-Ok "Transcripts will be saved to: $dataRoot"

# --- 7. Always-on auto-capture (logon task) ---
# A PowerShell script (not a native exe): a failure throws and $ErrorActionPreference
# halts us here, so no exit-code check is needed.
Write-Step "Registering the always-on auto-capture task"
& (Join-Path $RepoPath "installer\register-autocapture.ps1") -RepoPath $RepoPath

Write-Host ""
Write-Host "Install complete. Transcription is ON and always at the ready." -ForegroundColor Green
Write-Host ""
Write-Host "Turn it off for a private call, then back on:" -ForegroundColor White
Write-Host "  .\.venv\Scripts\python -m audio_transcriber teams-auto pause" -ForegroundColor Gray
Write-Host "  .\.venv\Scripts\python -m audio_transcriber teams-auto resume" -ForegroundColor Gray
Write-Host ""
