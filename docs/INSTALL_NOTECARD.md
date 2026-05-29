# Audio_Transcriber — Install Notecard

Pocket-sized reference for Tyler's on-site visit. Walks through every step in order, flags every permission gate, calls out the failure points.

**Repo:** https://github.com/tthompson0808/audio-transcriber
**Latest release:** https://github.com/tthompson0808/audio-transcriber/releases/latest
**Current version:** v0.1.1 — SHA-256 `84a2461425ce47e3226809a2798a497f1089c073c442ed89b5267760bdd6f65a`

---

## Pre-arrival (Tyler, day before visit)

| # | Step | Where | Permission |
|---|---|---|---|
| 1 | Create OpenAI account, generate API key, set $25/mo spending cap | platform.openai.com (CEO's email) | CEO must sign up; Tyler can screen-share |
| 2 | Create Anthropic account, generate API key, set $25/mo spending cap | console.anthropic.com (CEO's email) | Same as above |
| 3 | Register Microsoft Entra app for delegated Graph access | entra.microsoft.com → App registrations → New | **M365 admin only** (CEO if he's admin, or his IT person) |
| 4 | Note down the Entra app's **Client ID** and **Tenant ID** | After registration | — |
| 5 | Configure Entra app redirect URI: `http://localhost` (for device-code flow) | Authentication tab | M365 admin |
| 6 | Add delegated scopes to the Entra app | API permissions → Microsoft Graph → Delegated | M365 admin |
| | Scopes needed: `OnlineMeetings.Read`, `OnlineMeetingTranscript.Read.All`, `Calendars.Read`, `User.Read` | | |
| 7 | Grant admin consent for the four scopes | Same screen, "Grant admin consent" button | M365 admin |

---

## On-site visit (~60 minutes)

### 1 · Pre-flight check on CEO's Dell (5 min)

| Check | Command | If missing |
|---|---|---|
| Windows 11 | `winver` | Stop — needs Win 11 |
| OneDrive signed in | Look for OneDrive icon in tray | Sign him in first |
| ~5 GB free disk on C: | `Get-PSDrive C` in PowerShell | Free up space |
| Edge installed | (built into Win 11) | n/a |
| Claude Code installed | He says so / desktop shortcut | Install Claude Code first |

### 2 · Run the one-line installer (10–15 min)

**Open a regular (non-admin) PowerShell window** — Start menu → type "powershell" → Enter.

Paste this single line and press Enter:

```powershell
$z=$env:TEMP+'\at.ps1';Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/tthompson0808/audio-transcriber/releases/latest/download/bootstrap.ps1' -OutFile $z;powershell -ExecutionPolicy Bypass -File $z
```

**What it does (Tyler should narrate while it runs):**
1. Downloads `bootstrap.ps1` from GitHub Releases → `%TEMP%`
2. Bootstrap downloads the ZIP → `%LOCALAPPDATA%\Audio_Transcriber\src\` (no admin needed)
3. Bootstrap calls inner `install.ps1` which:
   - Detects Python 3.12+ (winget-installable if missing)
   - Creates venv at `%LOCALAPPDATA%\Audio_Transcriber\venv\`
   - `pip install` the package + 14 deps (anthropic, openai, fastapi, msal, httpx, keyring, psutil, pygetwindow, watchdog, pyaudiowpatch, pystray, pillow, win10toast-click, uvicorn) — ~2–3 min
   - Creates folders in OneDrive: `Audio_Transcriber\{meetings, Drop_Recordings, Drop_Transcripts, logs}\`
   - Registers 5 Windows Scheduled Tasks (user level, no admin):
     - `AudioTranscriber_AutoCapture` — at logon
     - `AudioTranscriber_GraphPoll` — every 5 min
     - `AudioTranscriber_Updater` — daily 03:00
     - `AudioTranscriber_Tray` — at logon
     - `AudioTranscriber_Dashboard` — at logon
   - Places desktop shortcut `Audio_Transcriber.lnk`
   - Starts Dashboard + Tray + AutoCapture tasks immediately

**Logs at:** `%LOCALAPPDATA%\Audio_Transcriber\logs\bootstrap_<YYYY-MM-DD>.log`

### 3 · First-time configuration (15 min)

Click the **Audio_Transcriber** desktop shortcut → opens Edge to `http://127.0.0.1:8765/`.

Go to **Settings** in the nav. Enter:

| Field | Value | Stored where |
|---|---|---|
| Anthropic Claude key | (the key from prep step 2) | Windows Credential Manager |
| OpenAI Whisper key | (the key from prep step 1) | Windows Credential Manager |
| Auto-record toggle | On (default) | `config.json` |
| Title exclusion patterns | Confirm: Board, HR, Legal, Privileged, 1:1 — ask CEO to add anything else | `config.json` |
| Attendee email blocklist | Add any "never record this person" domains | `config.json` |

Hit **Save**.

### 4 · Run Graph OAuth (one-time, ~3 min)

In PowerShell on CEO's laptop:

```powershell
& "$env:LOCALAPPDATA\Audio_Transcriber\venv\Scripts\python.exe" -m audio_transcriber graph-auth --client-id <CLIENT_ID> --tenant-id <TENANT_ID>
```

(Use the Client ID / Tenant ID from pre-arrival step 4.)

PowerShell will print a URL + device code. CEO opens the URL in any browser, enters the code, signs into his Microsoft account, consents. Refresh token persists to Windows Credential Manager.

**Required scopes** the consent screen will show (must all be ticked):
- Read your online meetings
- Read transcripts for online meetings
- Read your calendars
- Sign you in and read your profile

### 5 · Smoke test (10 min)

| Test | How | Expected |
|---|---|---|
| Dashboard reachable | Refresh `http://127.0.0.1:8765/` | Empty meetings list, no errors |
| Tray icon present | Look at system tray | Gray dot |
| Zoom auto-record | Start a 30-sec Zoom meeting with yourself | Toast appears, tray turns red, after meeting ends → red→yellow→gray, dashboard shows the entry within 1–2 min |
| Drop-zone audio | Drop any short m4a into `OneDrive\Audio_Transcriber\Drop_Recordings\` | New meeting appears in dashboard within 1–2 min |
| Drop-zone VTT | Drop any Teams VTT into `OneDrive\Audio_Transcriber\Drop_Transcripts\` | New meeting with speaker labels |
| Manual via Claude | Open Claude Code, say "start transcribing my meeting" → wait 10 sec → "stop transcribing" | Tray turns red then gray, new meeting in dashboard |
| Teams Graph pull | Run a real Teams meeting, wait 10 min | Meeting appears in dashboard automatically |

### 6 · Handoff (5 min)

- Walk through `docs/CEO_HANDOFF.md` (printed copy)
- Show: desktop shortcut, tray icon meaning, drop folders, dashboard
- Remind: red tray = recording, exclusion list editable in Settings
- Tell him: if anything breaks, screenshot + text Tyler

---

## Permission requirements summary

| Permission | Who needs it | Why |
|---|---|---|
| Admin on the Dell | **No** — entire install runs as user | Per-user scheduled tasks, %LOCALAPPDATA% install |
| Microsoft 365 admin | **Yes** — pre-arrival only | To register the Entra app + grant Graph consent |
| OpenAI account ownership | CEO | His billing surface |
| Anthropic account ownership | CEO | His billing surface |
| Screen Recording / Microphone | **No** | WASAPI loopback captures system audio without OS permission |
| OneDrive sign-in | Already signed in | Storage of meetings + drop folders |
| Tyler read-access to OneDrive log folder | Optional, post-install | Remote support — CEO grants via OneDrive share |

---

## Common failure modes + fixes

| Symptom | Fix |
|---|---|
| `Invoke-WebRequest : The remote name could not be resolved` | Check WiFi |
| `Cannot be loaded because running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force` then retry |
| `Python 3.12+ not found` | `winget install Python.Python.3.12 --scope user` then re-run installer |
| `pip` SSL errors | Corporate firewall — get pip behind their proxy: `pip config set global.proxy http://proxy.corp:8080` |
| OneDrive folder missing | Open OneDrive, sign in, wait for sync, re-run installer |
| Graph auth: `AADSTS65001 consent required` | Admin didn't grant consent in pre-arrival step 7 — go back and do it |
| Tray icon never appears | `Start-ScheduledTask AudioTranscriber_Tray` manually; check Task Scheduler |
| Dashboard 500 errors | `Get-Content "$env:LOCALAPPDATA\Audio_Transcriber\logs\bootstrap_*.log"` for clues |

---

## Uninstall (if needed)

```powershell
& "$env:LOCALAPPDATA\Audio_Transcriber\src\installer\uninstall.ps1"
# Or to also wipe OneDrive meeting data:
& "$env:LOCALAPPDATA\Audio_Transcriber\src\installer\uninstall.ps1" -WipeData
```

Stops + removes all five scheduled tasks, deletes the venv, removes the desktop shortcut, clears Credential Manager entries. Leaves OneDrive data intact by default so CEO's meeting history survives.
