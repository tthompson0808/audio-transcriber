# Audio_Transcriber — Claude Code Instructions

This file teaches Claude Code (running on the CEO's Windows laptop) how to drive Audio_Transcriber on the CEO's behalf. The CEO never types commands or opens a terminal — he talks to Claude in plain English and Claude calls the CLI.

## When the CEO says something like…

| He says | You run |
|---|---|
| "start transcribing my meeting" / "start recording" / "capture this call" | `python -m audio_transcriber meeting start` |
| "stop transcribing" / "stop recording" / "save the meeting" | `python -m audio_transcriber meeting stop` |
| "are you recording?" / "is anything being captured?" | `python -m audio_transcriber meeting status` |
| "open the dashboard" / "show me my meetings" | open `http://127.0.0.1:8765/` in his default browser |
| "what are my action items?" / "what's on my plate?" | `python -m audio_transcriber digest tasks` |
| "what did we decide about X?" | `python -m audio_transcriber digest decisions --since YYYY-MM-DD` or search by keyword |
| "what's my history with [person]?" | `python -m audio_transcriber digest person "Name"` |
| "search my meetings for X" | `python -m audio_transcriber transcript search "X"` |
| "import this VTT" (with a file path) | `python -m audio_transcriber ingest vtt "<path>"` |
| "import this transcript I pasted" | `python -m audio_transcriber ingest teams-paste "<path>"` |

## What happens automatically (no Claude action needed)

- **Teams meetings** — Microsoft Graph poller picks up new transcripts every 5 min. Don't try to "start recording" for a Teams meeting; it's already covered.
- **Zoom meetings** — auto-capture-runner detects `Zoom.exe` starting and records WASAPI loopback automatically. The tray icon turns red. If the CEO asks "is it recording?", check `meeting status` — if it shows ACTIVE, it's working.
- **Drop folders** — files dropped into `OneDrive\Audio_Transcriber\Drop_Recordings\` or `…\Drop_Transcripts\` are processed by the watchdog service.

## What NOT to do

- Don't restart Windows scheduled tasks unless asked.
- Don't delete files in `OneDrive\Audio_Transcriber\`.
- Don't run `digest rebuild` casually — it re-spends API tokens on every meeting.
- Don't ask the CEO to install anything. If a command fails because a package is missing, tell him to call Tyler.

## After running commands

- After `meeting start`: tell the CEO "Recording started. Just say 'stop transcribing' when you're done."
- After `meeting stop`: read the saved path back, then tell him to refresh the dashboard if he wants to see it.
- If a command fails, show the error output verbatim and tell him to send a screenshot to Tyler. Don't troubleshoot deeply — Tyler maintains this.

## API keys + auth

Keys live in Windows Credential Manager. If a command fails with "No Anthropic API key" or similar, the CEO can go to `http://127.0.0.1:8765/settings` and paste the key there. Don't ask him to set environment variables.
