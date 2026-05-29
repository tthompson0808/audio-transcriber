# Audio_Transcriber — Quick Reference

**Welcome.** This system listens for meetings, transcribes them, and feeds them into **Claude Desktop** on your laptop. Claude pulls out your action items, decisions, and key topics using your Pro/Max subscription — no per-API-call charges.

---

## How synthesis works

1. **Audio_Transcriber captures meetings** (Teams via Microsoft Graph, Zoom via auto-record, files you drop into OneDrive)
2. **Each meeting lands in a pending queue** with the raw transcript but no summary yet
3. **Claude Desktop processes the queue.** Open Claude Desktop and say:
   > "List pending meetings and synthesize them."
   Claude uses the audio_transcriber tools (built in during install) to read each transcript and write back the title, summary, action items, decisions, and topics.
4. **A safety net runs 3× daily** (7 am / 12:30 pm / 6 pm). If you've also given us an Anthropic API key, that runs the same processing via API in case Claude Desktop wasn't open. With no API key, the system just waits for you to open Claude Desktop.

---

## How to see your meetings

Click the **Audio_Transcriber** shortcut on your desktop. Your browser will open a dashboard listing every meeting, action item, and decision.

You can also filter action items by person, view recent decisions, or search across every transcript.

---

## What happens automatically

- **Microsoft Teams meetings** — picked up within ~10 minutes after the call ends.
- **Zoom meetings** — recorded automatically the moment Zoom starts. You'll see a notification ("Recording started — click to cancel") and a **red dot in your system tray** while recording is active.

---

## What you can do yourself

| You want to… | Do this |
|---|---|
| Have Claude Code record a meeting that isn't auto-detected | Open Claude Code, say "**start transcribing my meeting**" |
| Stop a recording | Say "**stop transcribing**" to Claude Code, OR right-click the tray icon → Stop Recording |
| Process pending meetings now (instead of waiting) | Open Claude Desktop, say "**list pending meetings and synthesize them**" |
| Add a recording from your phone or a saved Zoom file | Drag the file into `OneDrive\Audio_Transcriber\Drop_Recordings\` |
| Add a Teams transcript you exported | Drag the `.vtt` into `OneDrive\Audio_Transcriber\Drop_Transcripts\` |
| Stop everything temporarily | Right-click the tray icon → **Pause Auto-Capture** |

---

## The tray icon

A small dot sits next to your clock:

- **Gray** — idle
- **Red** — currently recording
- **Yellow** — uploading or processing

**Always glance at the tray before a sensitive conversation.** If it's red, recording is happening.

---

## Things to know

- **Recording consent.** Some states (California, Florida, others) require informing the other party that you're recording. The system records every Teams and Zoom meeting by default. If unsure, pause auto-capture before the call.
- **Excluded meetings.** During setup we configured the system to skip meetings whose title contains words like Board, HR, Legal, Privileged, 1:1. Edit any time at Settings.
- **Costs.** Audio transcription uses OpenAI Whisper (~$0.36/hr of audio). Synthesis uses your Claude Pro/Max plan via Claude Desktop — no per-meeting charge. Microsoft Graph is your existing M365.
- **Updates.** The system updates itself overnight. No action needed.
- **Tyler can see system health.** He has read-only access to a log folder in your OneDrive (no message content). This lets him fix issues before you notice them.

---

## Things to avoid

- **Don't move or rename** the `OneDrive\Audio_Transcriber\` folder.
- **Don't delete** the `digest.db` backup inside it.
- **Don't disable** the scheduled tasks named `AudioTranscriber_*`.
- **Don't disconnect** Claude Desktop from the audio_transcriber MCP server (you'll see it listed in Claude Desktop's settings under Developer / MCP).

---

## When something breaks

Call or text Tyler with:
- A screenshot of what you were trying to do
- The time it happened
- What you expected vs. what you got

Tyler can fix most things remotely.
