# Audio_Transcriber — nightly self-updater
# Pulls the latest GitHub Release tagged as `vX.Y.Z`, compares version, and
# updates the installed package via `pip install --upgrade`.
#
# Configuration: set $env:AT_GITHUB_REPO to "owner/repo" and (for private
# repos) $env:AT_GH_TOKEN to a fine-grained PAT with Releases:read.

[CmdletBinding()]
param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\Audio_Transcriber",
    [string]$Repo = $env:AT_GITHUB_REPO
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

if (-not $Repo) { $Repo = "tthompson0808/audio-transcriber" }

$logDir = Join-Path $env:OneDriveCommercial "Audio_Transcriber\logs"
if (-not (Test-Path $logDir)) { $logDir = Join-Path $env:USERPROFILE "Audio_Transcriber\logs" }
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logFile = Join-Path $logDir "update_$(Get-Date -Format yyyy-MM-dd).log"

function Log($msg) {
    "$(Get-Date -Format o)  $msg" | Tee-Object -FilePath $logFile -Append
}

Log "Update check started against $Repo"

$pyExe = Join-Path $InstallRoot "venv\Scripts\python.exe"
if (-not (Test-Path $pyExe)) {
    Log "ERROR: venv not found at $pyExe"
    exit 1
}

$current = & $pyExe -c "import audio_transcriber; print(audio_transcriber.__version__)" 2>$null
Log "Installed version: $current"

$headers = @{ "Accept" = "application/vnd.github+json" }
if ($env:AT_GH_TOKEN) { $headers["Authorization"] = "Bearer $env:AT_GH_TOKEN" }

try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers $headers
} catch {
    Log "ERROR: GitHub release lookup failed: $_"
    exit 1
}

$latest = $release.tag_name -replace "^v", ""
Log "Latest release: $latest"

if ($latest -eq $current) {
    Log "Already up to date."
    exit 0
}

# Find a wheel or sdist asset, or fall back to git+https
$asset = $release.assets | Where-Object { $_.name -like "*.whl" -or $_.name -like "*.tar.gz" } | Select-Object -First 1
if ($asset) {
    Log "Installing asset $($asset.name)"
    & (Join-Path $InstallRoot "venv\Scripts\pip.exe") install --upgrade --quiet $asset.browser_download_url
} else {
    Log "No wheel asset — installing from tag via git"
    & (Join-Path $InstallRoot "venv\Scripts\pip.exe") install --upgrade --quiet "git+https://github.com/$Repo@v$latest"
}

if ($LASTEXITCODE -ne 0) {
    Log "ERROR: pip install failed with exit $LASTEXITCODE"
    exit 1
}

$new = & $pyExe -c "import audio_transcriber; print(audio_transcriber.__version__)" 2>$null
Log "Updated to $new"

# Restart services so the new version takes effect
foreach ($t in @("AudioTranscriber_Dashboard", "AudioTranscriber_Tray", "AudioTranscriber_AutoCapture")) {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        Start-ScheduledTask -TaskName $t
        Log "Restarted $t"
    }
}

Log "Update complete."
