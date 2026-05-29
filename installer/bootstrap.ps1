# Audio_Transcriber — Windows bootstrap installer
#
# One-line install for the CEO. Downloads the latest release ZIP from GitHub,
# extracts it to %LOCALAPPDATA%\Audio_Transcriber\src\, then runs the bundled
# installer\install.ps1 from inside that folder.
#
# Usage (from a normal, non-admin PowerShell window):
#   .\bootstrap.ps1
#   .\bootstrap.ps1 -Force                       # reinstall over an existing install
#   .\bootstrap.ps1 -ZipUrl "https://..."        # override the release URL
#
# Logs to: %LOCALAPPDATA%\Audio_Transcriber\logs\bootstrap_<YYYY-MM-DD>.log
# On error, the log path is printed so it can be sent to Tyler.

[CmdletBinding()]
param(
    # URL of the release ZIP to download. Default points at the GitHub
    # "latest" release asset. {OWNER}/{REPO} are placeholders — replace
    # at release time, or pass -ZipUrl explicitly.
    [string]$ZipUrl = "https://github.com/{OWNER}/{REPO}/releases/latest/download/audio_transcriber-latest.zip",

    # Root install folder. Source code lands in $InstallRoot\src.
    [string]$InstallRoot = "$env:LOCALAPPDATA\Audio_Transcriber",

    # Reinstall over an existing $InstallRoot\src.
    [switch]$Force,

    # Passed through to install.ps1 — skips the Python 3.12+ check.
    [switch]$SkipPython
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# --- Paths ---
$srcDir   = Join-Path $InstallRoot "src"
$logDir   = Join-Path $InstallRoot "logs"
$tmpDir   = Join-Path $InstallRoot "tmp"
$logFile  = Join-Path $logDir ("bootstrap_{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
$zipFile  = Join-Path $tmpDir "audio_transcriber-latest.zip"

# Ensure log + tmp dirs exist before anything else can fail.
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

# --- Logging helpers ---
# Every Write-* helper tees to the log file so the full session is captured.
function Write-Log($line) {
    Add-Content -Path $logFile -Value ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $line)
}
function Write-Step($msg) {
    Write-Host "→ $msg" -ForegroundColor Cyan
    Write-Log  "STEP: $msg"
}
function Write-Ok($msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
    Write-Log  "OK:   $msg"
}
function Write-Warn($msg) {
    Write-Host "  ! $msg" -ForegroundColor Yellow
    Write-Log  "WARN: $msg"
}
function Write-Err($msg) {
    Write-Host "  ✗ $msg" -ForegroundColor Red
    Write-Log  "ERR:  $msg"
}

# --- Banner ---
Write-Host ""
Write-Host "Audio_Transcriber bootstrap" -ForegroundColor White
Write-Host "===========================" -ForegroundColor White
Write-Host ""
Write-Log  "=== Bootstrap started ==="
Write-Log  "ZipUrl=$ZipUrl"
Write-Log  "InstallRoot=$InstallRoot"
Write-Log  "Force=$Force  SkipPython=$SkipPython"

try {

    # --- 1. Handle existing install ---
    Write-Step "Checking for existing install at $srcDir"
    if (Test-Path $srcDir) {
        if (-not $Force) {
            Write-Warn "Audio_Transcriber appears to be already installed."
            Write-Host ""
            Write-Host "To reinstall / upgrade, re-run this script with -Force:" -ForegroundColor Yellow
            Write-Host "  .\bootstrap.ps1 -Force" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "(Existing install was left untouched.)" -ForegroundColor Yellow
            Write-Log "Existing install found, -Force not set — exiting cleanly."
            exit 0
        }
        Write-Warn "Existing install found — removing because -Force was specified."
        Remove-Item -Path $srcDir -Recurse -Force
        Write-Ok "Cleared $srcDir"
    } else {
        Write-Ok "No prior install — fresh setup"
    }

    # --- 2. Download release ZIP ---
    Write-Step "Downloading release ZIP"
    Write-Log "GET $ZipUrl"
    if (Test-Path $zipFile) { Remove-Item -Path $zipFile -Force }
    try {
        Invoke-WebRequest -Uri $ZipUrl -OutFile $zipFile -UseBasicParsing
    } catch {
        throw "Failed to download ZIP from $ZipUrl — $($_.Exception.Message)"
    }
    $zipSize = (Get-Item $zipFile).Length
    Write-Ok ("Downloaded {0:N0} bytes → {1}" -f $zipSize, $zipFile)

    # --- 3. Extract ZIP ---
    Write-Step "Extracting to $srcDir"
    New-Item -ItemType Directory -Path $srcDir -Force | Out-Null
    try {
        Expand-Archive -Path $zipFile -DestinationPath $srcDir -Force
    } catch {
        throw "Failed to extract ZIP — $($_.Exception.Message)"
    }

    # GitHub release ZIPs typically wrap contents in a single top-level
    # folder (e.g. "repo-1.2.3/"). If that's what we got, hoist its
    # contents up one level so install.ps1 lives at $srcDir\installer\.
    $topLevel = Get-ChildItem -Path $srcDir -Force
    if ($topLevel.Count -eq 1 -and $topLevel[0].PSIsContainer) {
        $inner = $topLevel[0].FullName
        Write-Log "ZIP wraps content in $($topLevel[0].Name) — hoisting up one level"
        Get-ChildItem -Path $inner -Force | Move-Item -Destination $srcDir -Force
        Remove-Item -Path $inner -Recurse -Force
    }
    Write-Ok "Extraction complete"

    # --- 4. Locate inner installer ---
    Write-Step "Locating inner installer"
    $innerInstaller = Join-Path $srcDir "installer\install.ps1"
    if (-not (Test-Path $innerInstaller)) {
        throw "Could not find installer\install.ps1 inside the extracted ZIP. Expected at: $innerInstaller"
    }
    Write-Ok "Found $innerInstaller"

    # --- 5. Run inner installer ---
    Write-Step "Running inner installer (this can take a few minutes)"
    Write-Log "Invoking: powershell -NoProfile -ExecutionPolicy Bypass -File $innerInstaller -RepoPath $srcDir -InstallRoot $InstallRoot"

    # Build arg list — pass -SkipPython through if it was set on bootstrap.
    $innerArgs = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $innerInstaller,
        "-RepoPath", $srcDir,
        "-InstallRoot", $InstallRoot
    )
    if ($SkipPython) { $innerArgs += "-SkipPython" }

    # Run in the same console so the CEO sees install.ps1's own progress
    # output. Tee the inner output to our log file as well.
    $innerLog = Join-Path $logDir ("install_{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HHmmss"))
    & powershell.exe @innerArgs 2>&1 | Tee-Object -FilePath $innerLog | ForEach-Object {
        Write-Host $_
        Add-Content -Path $logFile -Value "  | $_"
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Inner installer exited with code $LASTEXITCODE — see $innerLog"
    }
    Write-Ok "Inner installer finished cleanly"

    # --- 6. Cleanup ---
    Write-Step "Cleaning up temp files"
    try {
        Remove-Item -Path $zipFile -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Warn "Could not remove $zipFile — safe to ignore"
    }
    Write-Ok "Done"

    Write-Host ""
    Write-Host "Bootstrap complete." -ForegroundColor Green
    Write-Host "Log: $logFile" -ForegroundColor DarkGray
    Write-Host ""
    Write-Log "=== Bootstrap finished successfully ==="
    exit 0

} catch {
    $errMsg = $_.Exception.Message
    Write-Host ""
    Write-Err "Bootstrap failed: $errMsg"
    Write-Log "FATAL: $errMsg"
    Write-Log "STACK: $($_.ScriptStackTrace)"
    Write-Host ""
    Write-Host "Something went wrong during install." -ForegroundColor Red
    Write-Host "Please send this log file to Tyler:" -ForegroundColor Yellow
    Write-Host "  $logFile" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
