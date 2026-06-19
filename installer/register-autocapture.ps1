# Audio_Transcriber - register the always-on auto-capture.
#
# Tries a logon Scheduled Task first (best: restart-on-crash, battery-aware).
# On a locked-down / MDM-managed machine where task creation is denied without
# admin (HRESULT 0x80070005), falls back to a per-user Startup shortcut, which
# needs no admin. Either way the capture loop runs at every logon and is ON by
# default, and is started immediately. Keyless. Safe to re-run.
#
#   powershell -ExecutionPolicy Bypass -File .\installer\register-autocapture.ps1
#
[CmdletBinding()]
param(
    [string]$RepoPath = "",
    [string]$TaskName = "AudioTranscriber_AutoCapture"
)
$ErrorActionPreference = "Stop"

if (-not $RepoPath) {
    # Resolve <repo> as the parent of this script's installer/ folder, in the body
    # (not the param default) because $PSScriptRoot can be empty in a param default
    # depending on how PowerShell launched the script.
    $here = $PSScriptRoot
    if (-not $here -and $PSCommandPath) { $here = Split-Path -Parent $PSCommandPath }
    if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }
    $RepoPath = Split-Path -Parent $here
}

$pyExe  = Join-Path $RepoPath ".venv\Scripts\python.exe"
$pywExe = Join-Path $RepoPath ".venv\Scripts\pythonw.exe"   # windowless, for background runs
if (-not (Test-Path $pyExe)) {
    throw "Virtual env not found at $pyExe. Run the install steps first (create .venv)."
}
$runExe = if (Test-Path $pywExe) { $pywExe } else { $pyExe }

# Stop any loop already running, so we never end up with two grabbing the mic.
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'audio_transcriber.*(autocapture|teams-auto)' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

function Start-Loop-Now {
    # Launch the capture loop immediately, hidden, so it is on without a re-logon.
    # autocapture = the logged, windowless wrapper around `teams-auto serve`.
    Start-Process -FilePath $runExe -ArgumentList "-m audio_transcriber.autocapture" `
        -WorkingDirectory $RepoPath -WindowStyle Hidden | Out-Null
}

function Install-StartupShortcut {
    # Per-user Startup folder: runs at every logon, no admin required.
    $startup = [Environment]::GetFolderPath("Startup")
    $lnkPath = Join-Path $startup "AudioTranscriber.lnk"
    $ws  = New-Object -ComObject WScript.Shell
    $lnk = $ws.CreateShortcut($lnkPath)
    $lnk.TargetPath       = $runExe
    $lnk.Arguments        = "-m audio_transcriber.autocapture"
    $lnk.WorkingDirectory = $RepoPath
    $lnk.WindowStyle      = 7   # minimized / hidden
    $lnk.Description       = "Audio Transcriber auto-capture (keyless)"
    $lnk.Save()
    return $lnkPath
}

$method = $null
try {
    # Use pythonw ($runExe), not python.exe ($pyExe): an admin-created task otherwise
    # flashes a console window at every (re)start. autocapture = the logged wrapper.
    $action  = New-ScheduledTaskAction -Execute $runExe -Argument "-m audio_transcriber.autocapture"
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    $settings.ExecutionTimeLimit = "PT0S"   # no time limit: the loop runs continuously

    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    }
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -RunLevel Limited `
        -Description "Auto-capture Teams meetings (Option B: stereo, on-device, keyless)" | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    $method = "scheduled task '$TaskName'"
} catch {
    $first = (($_.Exception.Message -split "`n")[0]).Trim()  # strip trailing CR so the line prints cleanly
    Write-Host "  Scheduled task not permitted on this machine ($first)." -ForegroundColor Yellow
    Write-Host "  Using a per-user Startup shortcut instead (no admin needed)." -ForegroundColor Yellow
    $lnk = Install-StartupShortcut
    Start-Loop-Now
    $method = "Startup shortcut ($lnk)"
}

Write-Host ""
Write-Host "Always-on auto-capture is set via $method, and started now." -ForegroundColor Green
Write-Host "Transcription is ON and comes back at every logon." -ForegroundColor Green
Write-Host ""
Write-Host "Turn it off for a private call, then back on:" -ForegroundColor White
Write-Host "  .\.venv\Scripts\python -m audio_transcriber teams-auto pause" -ForegroundColor Gray
Write-Host "  .\.venv\Scripts\python -m audio_transcriber teams-auto resume" -ForegroundColor Gray
Write-Host ""
