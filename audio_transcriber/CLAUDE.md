# Audio_Transcriber — Claude Code Instructions

This file teaches Claude Code (running on the CEO's Windows laptop) how to drive Audio_Transcriber on the CEO's behalf. The CEO never types commands or opens a terminal — he talks to Claude in plain English and Claude calls the CLI.

> **Synthesis architecture:** Audio_Transcriber captures meetings and queues them for synthesis. Primary synthesis runs in **Claude Desktop** (a different app from Claude Code) via the audio_transcriber MCP server — it uses the CEO's Pro/Max subscription, not an API key. A scheduled fallback runs 3x/day to drain the queue via the Anthropic API IF a key is configured.

## When the CEO says something like…

| He says | You run |
|---|---|
| "start transcribing my meeting" / "capture this call" | `python -m audio_transcriber meeting start` |
| "stop transcribing" / "save the meeting" | `python -m audio_transcriber meeting stop` |
| "are you recording?" / "is anything being captured?" | `python -m audio_transcriber meeting status` |
| "turn off transcription" / "stop auto-recording my meetings" | `python -m audio_transcriber teams-auto pause` |
| "turn transcription back on" / "resume auto-recording" | `python -m audio_transcriber teams-auto resume` |
| "is auto-transcription on?" | `python -m audio_transcriber teams-auto status` |
| "open the dashboard" / "show me my meetings" | open `http://127.0.0.1:8765/` in his default browser |
| "what's pending synthesis?" / "anything not processed?" | `python -m audio_transcriber synthesize-pending --dry-run` |
| "process pending meetings" / "digest the queue" | Tell him to open **Claude Desktop** and ask "list pending meetings and synthesize them" — that path uses his Pro/Max quota |
| "what are my action items?" | `python -m audio_transcriber digest tasks` |
| "what did we decide about X?" | `python -m audio_transcriber digest decisions` (or search by keyword) |
| "what's my history with [person]?" | `python -m audio_transcriber digest person "Name"` |
| "search my meetings for X" | `python -m audio_transcriber transcript search "X"` |
| "import this VTT" (with a file path) | `python -m audio_transcriber ingest vtt "<path>"` |
| "import this pasted transcript" | `python -m audio_transcriber ingest teams-paste "<path>"` |

## What happens automatically (no Claude action needed)

- **Teams meetings** — the always-on auto-capture loop detects when Teams is in a call (mic in use), records both sides in stereo (his mic + the other participants), transcribes on-device with no API key, and queues the meeting as pending. It is **ON at every startup**; the CEO can turn it off/on with the commands above (off persists until he turns it back on or the laptop restarts).
- **Zoom meetings** — auto-capture-runner detects `Zoom.exe` and records WASAPI loopback. After it ends, Whisper transcribes and the meeting is queued as pending.
- **Drop folders** — files dropped into `OneDrive\Audio_Transcriber\Drop_Recordings\` or `…\Drop_Transcripts\` are processed by the watchdog service and queued.
- **3x-daily fallback** (07:00, 12:30, 18:00) — `AudioTranscriber_SynthFallback` scheduled task drains the queue via Anthropic API IF a key is configured. If no key, queue waits for Claude Desktop.

## Pending vs synthesized

Every meeting has a `synthesized: true/false` flag in its JSON. A meeting is "pending" until Claude Desktop (or the API fallback) fills in the title, summary, action items, decisions, and topics. The dashboard's Recent Meetings list shows pending ones with placeholder titles.

If the CEO asks "why does this meeting look empty?" — the answer is: it hasn't been synthesized yet. Tell him to open Claude Desktop and ask it to process pending meetings.

## What NOT to do

- Don't restart Windows scheduled tasks unless asked.
- Don't delete files in `OneDrive\Audio_Transcriber\`.
- Don't run `digest rebuild` casually — it re-spends tokens/quota on every meeting.
- Don't ask the CEO to install anything. If a command fails because a package is missing, tell him to call Tyler.

## After running commands

- After `meeting start`: tell him "Recording started. Just say 'stop transcribing' when you're done."
- After `meeting stop`: read the saved path back, then tell him the meeting is queued and will be synthesized by Claude Desktop (or the next scheduled fallback run).
- If a command fails, show the error output verbatim and tell him to send a screenshot to Tyler.

## API keys + auth

- **OpenAI Whisper key** — required for audio inflows. Set via `http://127.0.0.1:8765/settings`.
- **Anthropic Claude key** — OPTIONAL. Only needed for the 3x-daily API fallback. Primary synthesis is Claude Desktop.
- **Microsoft Graph** — already authenticated during install (refresh token in Credential Manager).
