# Audio_Transcriber — uninstaller
# Stops + removes scheduled tasks, deletes the venv and config dir,
# removes the desktop shortcut. LEAVES OneDrive data intact by default
# so the CEO doesn't lose meeting history. Pass -WipeData to nuke that too.

[CmdletBinding()]
param(
    [switch]$WipeData,
    [string]$InstallRoot = "$env:LOCALAPPDATA\Audio_Transcriber",
    [string]$ConfigRoot = "$env:APPDATA\Audio_Transcriber"
)

$ErrorActionPreference = "Continue"

Write-Host "Uninstalling Audio_Transcriber…" -ForegroundColor Cyan

foreach ($t in @(
    "AudioTranscriber_AutoCapture",
    "AudioTranscriber_GraphPoll",
    "AudioTranscriber_Updater",
    "AudioTranscriber_Tray",
    "AudioTranscriber_Dashboard"
)) {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "  Removed task $t"
    }
}

if (Test-Path $InstallRoot) {
    Remove-Item -Path $InstallRoot -Recurse -Force
    Write-Host "  Removed $InstallRoot"
}

if (Test-Path $ConfigRoot) {
    Remove-Item -Path $ConfigRoot -Recurse -Force
    Write-Host "  Removed $ConfigRoot"
}

$shortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "Audio_Transcriber.lnk"
if (Test-Path $shortcut) {
    Remove-Item $shortcut
    Write-Host "  Removed desktop shortcut"
}

if ($WipeData) {
    $onedrive = $env:OneDriveCommercial
    if (-not $onedrive) { $onedrive = $env:OneDrive }
    if ($onedrive) {
        $dataRoot = Join-Path $onedrive "Audio_Transcriber"
        if (Test-Path $dataRoot) {
            Remove-Item -Path $dataRoot -Recurse -Force
            Write-Host "  WIPED OneDrive data folder $dataRoot" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  OneDrive meeting data left in place. Pass -WipeData to remove."
}

# Remove credentials. Best-effort — leftovers in Credential Manager are harmless.
foreach ($name in @("anthropic_api_key", "openai_api_key", "graph_refresh_token", "graph_client_id", "graph_tenant_id")) {
    cmdkey /delete:"Audio_Transcriber/$name" 2>$null | Out-Null
}

Write-Host "Done." -ForegroundColor Green
