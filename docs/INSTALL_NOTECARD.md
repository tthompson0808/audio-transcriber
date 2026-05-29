# Audio_Transcriber — Install Notecard (v0.2.0)

Pocket-sized reference for Tyler's on-site visit. **Architecture changed in v0.2.0:** primary synthesis now runs in **Claude Desktop** on the CEO's machine using his Pro/Max subscription, not the Anthropic API. The Anthropic key is optional — only needed for the 3×-daily safety-net runner.

**Repo:** https://github.com/tthompson0808/audio-transcriber
**Latest release:** https://github.com/tthompson0808/audio-transcriber/releases/latest

---

## Pre-arrival (Tyler, day before visit)

| # | Step | Where | Permission |
|---|---|---|---|
| 1 | Confirm CEO has **Claude Desktop** installed and is signed in with **Pro or Max plan** | claude.ai/download · Settings → Subscription | CEO |
| 2 | Confirm **Claude Code** is installed (for the manual `meeting start` trigger) | claude.ai/download/code | CEO |
| 3 | Create **OpenAI account**, generate API key, set $25/mo spending cap | platform.openai.com | CEO — needed for Whisper |
| 4 | *(Optional)* Create **Anthropic API account** + key for the 3×-daily fallback runner | console.anthropic.com | CEO — skip if you want Claude-Desktop-only |
| 5 | Register **Microsoft Entra app** for delegated Graph access | entra.microsoft.com → App registrations → New | **M365 admin only** |
| 6 | Note down the Entra app's **Client ID** and **Tenant ID** | After registration | — |
| 7 | Configure redirect URI: `http://localhost` (device-code flow) | Authentication tab | M365 admin |
| 8 | Add delegated scopes: `OnlineMeetings.Read`, `OnlineMeetingTranscript.Read.All`, `Calendars.Read`, `User.Read` | API permissions → Microsoft Graph → Delegated | M365 admin |
| 9 | Click **Grant admin consent** for all four | Same screen | M365 admin |

---

## On-site visit (~60 minutes)

### 1 · Pre-flight check on CEO's Dell (5 min)

| Check | Command | If missing |
|---|---|---|
| Windows 11 | `winver` | Stop — needs Win 11 |
| OneDrive signed in | OneDrive icon in tray | Sign in first |
| ~5 GB free on C: | `Get-PSDrive C` | Free up space |
| Claude Desktop installed + signed in | Open the app | Install from claude.ai/download |
| Claude Code installed | Desktop icon | Install from claude.ai/download/code |

### 2 · Run the one-line installer (10–15 min)

**Open a regular (non-admin) PowerShell window.** Paste:

```powershell
$z=$env:TEMP+'\at.ps1';Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/tthompson0808/audio-transcriber/releases/latest/download/bootstrap.ps1' -OutFile $z;powershell -ExecutionPolicy Bypass -File $z
```

**What scrolls past (narrate it while it runs):**
1. Downloads `bootstrap.ps1` → `%TEMP%`
2. Bootstrap downloads the ZIP → `%LOCALAPPDATA%\Audio_Transcriber\src\`
3. Inner `install.ps1` runs:
   - Detects Python 3.12+ (winget-installable if missing)
   - Creates venv at `%LOCALAPPDATA%\Audio_Transcriber\venv\`
   - `pip install` 15 deps including the **mcp[cli]** package — ~2–3 min
   - Creates OneDrive folders: `Audio_Transcriber\{meetings, Drop_Recordings, Drop_Transcripts, logs}\`
   - Registers **6 Windows Scheduled Tasks**:
     - `AudioTranscriber_AutoCapture` — at logon (Zoom watcher)
     - `AudioTranscriber_GraphPoll` — every 5 min (Teams transcripts)
     - `AudioTranscriber_Tray` — at logon (system tray icon)
     - `AudioTranscriber_Dashboard` — at logon (localhost:8765)
     - **`AudioTranscriber_SynthFallback`** — 7am / 12:30pm / 6pm (API fallback)
     - `AudioTranscriber_Updater` — daily 03:00
   - **Registers `audio_transcriber` MCP server with Claude Desktop** by merging into `%APPDATA%\Claude\claude_desktop_config.json` (preserves any other MCP servers)
   - Places desktop shortcut + starts services

**Logs at:** `%LOCALAPPDATA%\Audio_Transcriber\logs\bootstrap_<date>.log`

### 3 · Restart Claude Desktop (1 min)

Quit Claude Desktop fully and reopen it. In Settings → Developer → MCP, you should see `audio_transcriber` listed as connected. Without this restart, Claude won't see the new tools.

### 4 · First-time dashboard configuration (10 min)

Click the **Audio_Transcriber** desktop shortcut → opens Edge to `http://127.0.0.1:8765/`.

Go to **Settings**:

| Field | Required? | Value |
|---|---|---|
| **OpenAI Whisper key** | **Yes** | From pre-arrival step 3 |
| Anthropic Claude key | Optional | From pre-arrival step 4 (skip if Claude-Desktop-only) |
| Auto-record toggle | Default On | — |
| Title exclusion patterns | Confirm | Board, HR, Legal, Privileged, 1:1 + anything CEO adds |
| Attendee email blocklist | Confirm | Domains that should never be recorded |

Hit **Save**.

### 5 · Graph OAuth one-time (3 min)

In PowerShell:

```powershell
& "$env:LOCALAPPDATA\Audio_Transcriber\venv\Scripts\python.exe" -m audio_transcriber graph-auth --client-id <CLIENT_ID> --tenant-id <TENANT_ID>
```

PowerShell prints a URL + device code. CEO completes the flow in Edge. Required scopes (all must be ticked on the consent screen):
- Read your online meetings
- Read transcripts for online meetings
- Read your calendars
- Sign you in and read your profile

### 6 · Smoke test (15 min)

| Test | How | Expected |
|---|---|---|
| Dashboard reachable | Refresh `http://127.0.0.1:8765/` | Empty meetings list, no errors |
| Tray icon present | System tray | Gray dot |
| Claude Desktop sees MCP | Open Claude Desktop → Settings → Developer → MCP | `audio_transcriber` listed as connected |
| **Synthesis via Claude Desktop** | In Claude Desktop, say: "List pending meetings using the audio_transcriber tools." | Returns a list (initially empty) |
| Zoom auto-record | Start a 30-sec Zoom with yourself | Toast + red tray, meeting appears in dashboard as **pending** within ~1 min |
| Synthesize the test meeting | In Claude Desktop: "Synthesize all pending meetings." | Dashboard meeting now shows title, summary, action items |
| Drop-zone audio | Drop a short .m4a into `Drop_Recordings\` | New pending meeting within ~1 min |
| Manual via Claude Code | In Claude Code: "start transcribing my meeting" → wait → "stop transcribing" | Tray red→gray, pending meeting in dashboard |
| Real Teams meeting | Run a real Teams call, wait 10 min | Pending meeting appears via Graph |

### 7 · Handoff (5 min)

- Walk through `docs/CEO_HANDOFF.md` (printed)
- Show: shortcut, tray, drop folders, Claude Desktop synthesis prompt
- Demo: "list pending meetings and synthesize them" in Claude Desktop
- Remind: red tray = recording; exclusion list editable in Settings

---

## Permission requirements summary

| Permission | Who needs it | Why |
|---|---|---|
| Admin on the Dell | **No** | Per-user scheduled tasks, %LOCALAPPDATA% install |
| Microsoft 365 admin | **Yes** — pre-arrival only | Entra app registration + Graph consent |
| Claude Pro/Max plan | **Yes** | Primary synthesis runs through CEO's Claude Desktop quota |
| OpenAI account | CEO | Whisper billing |
| Anthropic account | Optional | Only if running the API fallback |
| Screen Recording / Microphone | **No** | WASAPI loopback captures system audio without OS permission |
| OneDrive sign-in | Already signed in | Storage for meetings + drop folders |
| Tyler read-access to OneDrive log folder | Optional, post-install | Remote support |

---

## Common failure modes + fixes

| Symptom | Fix |
|---|---|
| `Invoke-WebRequest : The remote name could not be resolved` | Check WiFi |
| `Cannot be loaded because running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force` then retry |
| `Python 3.12+ not found` | `winget install Python.Python.3.12 --scope user` then re-run installer |
| OneDrive folder missing | Open OneDrive, sign in, wait for sync, re-run installer |
| Claude Desktop doesn't see `audio_transcriber` MCP | Fully quit Claude Desktop (tray icon → Quit), reopen. If still missing: re-run `python -m audio_transcriber claude-config` |
| Meetings stay "pending" forever | Either ask Claude Desktop to synthesize them, OR set the Anthropic API key in Settings so the 3×-daily fallback runs |
| Graph auth: `AADSTS65001 consent required` | Admin consent missing — pre-arrival step 9 |
| Tray icon never appears | `Start-ScheduledTask AudioTranscriber_Tray`, check Task Scheduler |
| Dashboard 500 errors | `Get-Content "$env:LOCALAPPDATA\Audio_Transcriber\logs\bootstrap_*.log"` |

---

## Uninstall

```powershell
& "$env:LOCALAPPDATA\Audio_Transcriber\src\installer\uninstall.ps1"
# Or to also wipe OneDrive meeting data:
& "$env:LOCALAPPDATA\Audio_Transcriber\src\installer\uninstall.ps1" -WipeData
```

Removes all scheduled tasks, venv, desktop shortcut, Credential Manager entries. **Note:** the uninstaller does not currently strip the `audio_transcriber` entry from Claude Desktop's config — remove manually from `%APPDATA%\Claude\claude_desktop_config.json` if desired.
