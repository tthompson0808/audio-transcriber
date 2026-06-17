# Audio_Transcriber - register the always-on auto-capture task.
#
# Registers a logon-triggered Scheduled Task that runs the Option B capture
# loop (`teams-auto serve`), so transcription is always at the ready and comes
# back automatically after a restart. Keyless. Safe to re-run (idempotent).
#
# Run as the laptop owner (no admin needed), from the repo root:
#   powershell -ExecutionPolicy Bypass -File .\installer\register-autocapture.ps1
#
[CmdletBinding()]
param(
    [string]$RepoPath = (Split-Path -Parent $PSScriptRoot),   # parent of installer/
    [string]$TaskName = "AudioTranscriber_AutoCapture"
)
$ErrorActionPreference = "Stop"

$pyExe = Join-Path $RepoPath ".venv\Scripts\python.exe"
if (-not (Test-Path $pyExe)) {
    throw "Virtual env not found at $pyExe. Run the install steps first (create .venv)."
}

$action  = New-ScheduledTaskAction -Execute $pyExe -Argument "-m audio_transcriber teams-auto serve"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$settings.ExecutionTimeLimit = "PT0S"   # no time limit: the capture loop runs continuously

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -RunLevel Limited `
    -Description "Auto-capture Teams meetings (Option B: stereo, on-device, keyless)" | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Host ""
Write-Host "Registered and started '$TaskName'." -ForegroundColor Green
Write-Host "Transcription now starts at every logon and is ON by default." -ForegroundColor Green
Write-Host ""
Write-Host "Turn it off for a private call, then back on:" -ForegroundColor White
Write-Host "  .\.venv\Scripts\python -m audio_transcriber teams-auto pause" -ForegroundColor Gray
Write-Host "  .\.venv\Scripts\python -m audio_transcriber teams-auto resume" -ForegroundColor Gray
Write-Host "  .\.venv\Scripts\python -m audio_transcriber teams-auto status" -ForegroundColor Gray
Write-Host ""
