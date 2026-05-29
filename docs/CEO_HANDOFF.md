# Audio_Transcriber — Quick Reference

**Welcome.** This system listens for meetings, transcribes them, and pulls out your action items and decisions automatically. Here's everything you need to know.

---

## How to see your meetings

Click the **Audio_Transcriber** shortcut on your desktop. Your browser will open a dashboard listing every meeting, action item, and decision.

You can also see action items by topic, person, or due date.

---

## What happens automatically — without you doing anything

- **Microsoft Teams meetings** — picked up within about 10 minutes after the call ends. Includes who said what.
- **Zoom meetings** — recorded automatically the moment Zoom starts. You'll see a quick notification ("Recording started — click to cancel") and a **red dot in your system tray** while recording is active.

---

## What you can do yourself

| You want to… | Do this |
|---|---|
| Have Claude record a meeting that isn't being caught automatically | Open Claude Code and say "**start transcribing my meeting**" |
| Stop a recording | Say "**stop transcribing**" to Claude, OR right-click the tray icon and choose Stop Recording |
| Add a recording from your phone, a voice recorder, or a saved Zoom file | Drag the file into `OneDrive\Audio_Transcriber\Drop_Recordings\` |
| Add a Teams transcript file you exported | Drag the `.vtt` file into `OneDrive\Audio_Transcriber\Drop_Transcripts\` |
| Stop everything temporarily | Right-click the tray icon → **Pause Auto-Capture** |

---

## The tray icon

A small dot sits next to your clock. Its color tells you what's happening:

- **Gray** — idle, nothing recording
- **Red** — currently recording
- **Yellow** — uploading or processing a recording

**Always glance at the tray before a sensitive conversation.** If it's red, recording is happening.

---

## Things you should know

- **Recording consent.** In some states (California, Florida, others) recording a call requires informing the other party. The system records every Teams and Zoom meeting by default. If you're not sure, pause auto-capture before the call.
- **Excluded meetings.** During setup we configured the system to skip meetings whose title contains words like Board, HR, Legal, Privileged, 1:1. You can edit that list any time in the dashboard's Settings page.
- **API costs.** The system uses three accounts billed to you: Anthropic, OpenAI, and your Microsoft 365 subscription. Anthropic and OpenAI charge roughly a few cents per meeting — plan on $20–40/month combined at normal use. Spending caps are set on each account.
- **Updates.** The system updates itself overnight. No action needed.
- **Tyler can see system health.** He has read-only access to a log folder in your OneDrive (no message content, just error counts and timestamps). This lets him fix issues before you notice them.

---

## Things to avoid

- **Don't move or rename** the `OneDrive\Audio_Transcriber\` folder.
- **Don't delete** the `digest.db` backup inside it.
- **Don't disable** the scheduled tasks named `AudioTranscriber_*` — they keep everything running.

---

## When something breaks

Call or text Tyler. Include:
- A screenshot of the dashboard or whatever you were trying to do
- The time it happened
- What you were expecting vs. what you saw

Tyler can fix most things remotely.
