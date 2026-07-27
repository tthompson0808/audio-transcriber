# Audio_Transcriber

Windows port of Tyler's macOS AudioTools, deployable to non-technical clients (initially: small-business CEOs). Captures meetings four ways, runs them through Whisper + Claude, and writes structured tasks/decisions/topics into a queryable SQLite digest with column-identical schema to Tyler's own AudioTools digest.

## Architecture

Four inflow pipelines feed one queue → synthesis → storage + digest:
1. **Microsoft Graph poller** — pulls Teams transcripts (with speaker labels) every 5 min
2. **WASAPI auto-record** — detects Zoom.exe and captures system audio → Whisper (on-device by default)
3. **Drag-drop audio/video** — `OneDrive\Audio_Transcriber\Drop_Recordings\` → Whisper (on-device by default)
4. **Drag-drop VTT or paste-text** — `OneDrive\Audio_Transcriber\Drop_Transcripts\` → parser

Plus a manual trigger via Claude Code on the CEO's laptop: he says "start transcribing my meeting" and Claude runs the CLI.

## Project layout

```
audio_transcriber/
  capture/          process detector, WASAPI recorder, Graph poller, dropzone watcher, dedup, exclusion, meeting orchestrator
  transcribe/       on-device faster-whisper + Whisper API client + router + echo cancellation
  synthesize/       speaker-aware Claude summarizer
  ingest/           VTT and Teams-paste parsers + ingest pipelines
  digest/           SQLite DDL + writer + queries (column-identical to Tyler's AudioTools)
  storage/          per-meeting JSON writer + flat index
  dashboard/        FastAPI on 127.0.0.1:8765 with Tailwind templates
  auth/             Windows Credential Manager (via keyring)
  tray.py           pystray system-tray icon (gray/red/yellow states)
  auto_capture_runner.py   long-running process-detector loop launched at logon
  cli.py            argparse entry — what Claude Code invokes
  CLAUDE.md         instructions for Claude Code on the client's machine
installer/
  bootstrap.ps1     one-line clone + install (pipe to iex), no admin required
  install.ps1       provisions venv + scheduled tasks + shortcut + folders
  register-autocapture.ps1  always-on capture at logon (scheduled task, Startup-shortcut fallback)
  update_check.ps1  nightly self-updater (GitHub Releases)
  uninstall.ps1     clean teardown (keeps OneDrive data by default)
docs/
  CEO_HANDOFF.md    printable one-pager for the client
  CLIENT_INSTALL.md client-facing install guide
  INSTALL_NOTECARD.md  pocket reference for on-site installs
tests/              schema parity, parsers, exclusion, dedup, OneDrive stability, speaker branching
```

## Status

Built on Tyler's Mac — all code present and unit tests are runnable here. End-to-end verification of Windows-only pieces (WASAPI capture, pystray tray, PowerShell installer, scheduled tasks) requires a Windows 11 VM or the client's actual laptop.

### Verified on Mac
- All ported parsers, summarizer, digest pipeline, storage writer
- Dedup logic
- Exclusion rules
- Dashboard renders against a seeded DB
- Schema parity test passes against Tyler's `~/AudioTools/src/digest/db.py`

### Needs a Windows machine to verify
- WASAPI loopback capture (pyaudiowpatch import-guarded; will fail import on macOS until run on Windows)
- System tray icon (pystray Win32 backend)
- Process detector (psutil works on both, but Zoom.exe only exists on Win)
- `pygetwindow` (window-title-based exclusion)
- PowerShell installer + scheduled tasks
- Toast notifications

### Per-inflow happy-path tests
- VTT and paste-text parsing: covered by `test_parsers.py`
- Graph poller: requires real OAuth — manual smoke test on first install
- WASAPI + Whisper: requires Windows + a recording — smoke test on install day
- Dropzone watcher: covered by `test_dropzone_stability.py` (file-stability gate)

## Running tests

```
pip install -e ".[test]"
pytest -v
```

The schema-parity test reads from `/Users/tyler/AudioTools/src/digest/db.py` to compare DDL. If that path isn't present, the test skips.

## Install on a client laptop

See [docs/CEO_HANDOFF.md](docs/CEO_HANDOFF.md) for the CEO-facing one-pager.

Short version:
```powershell
git clone https://github.com/tthompson0808/audio-transcriber C:\src\audio-transcriber
cd C:\src\audio-transcriber\installer
.\install.ps1
```
Then open `http://127.0.0.1:8765/settings` to enter API keys, and run the Graph OAuth flow:
```powershell
C:\src\audio-transcriber\.venv\Scripts\python.exe `
    -m audio_transcriber graph-auth --client-id <ID> --tenant-id <TENANT>
```
