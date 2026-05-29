# Audio Transcriber — Install Guide

This is everything you need to install Audio Transcriber on your PC. Should take about 5 minutes. You do **not** need IT or admin rights.

## Before you start

Make sure these two are installed and signed in:

- **Claude Desktop** — download from [claude.ai/download](https://claude.ai/download). Sign in with the Claude account that has your Pro or Max plan. Audio Transcriber will plug into Claude Desktop and use your existing plan to process meetings.
- **Claude Code** — also from [claude.ai/download/code](https://claude.ai/download/code). Same login. This is what you'll use to start/stop recording on demand.

You'll also need an **OpenAI API key** (for transcribing audio to text). We sent it to you with this email; if not, sign up at [platform.openai.com](https://platform.openai.com), generate a key, set a $25/mo cap.

---

## 1. Install command

Open **PowerShell** (press the Windows key, type `PowerShell`, hit Enter — the regular blue one, not "as Administrator").

Copy the line below, paste it into PowerShell, and press Enter:

```powershell
$z=$env:TEMP+'\at.ps1';Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/tthompson0808/audio-transcriber/releases/latest/download/bootstrap.ps1' -OutFile $z;powershell -ExecutionPolicy Bypass -File $z
```

That's the whole install. Sit back.

---

## 2. What you will see

The window will show progress messages as it works through these steps:

1. **Downloading Audio Transcriber** — the app package pulls down from GitHub.
2. **Checking for Python** — required runtime. If missing, the installer fetches it for you.
3. **Unpacking files** — installs into your user folder (no admin needed).
4. **Setting up OneDrive sync folder** — so your transcripts back up automatically.
5. **Creating desktop shortcut** — for one-click launch.
6. **Starting the app** — opens the dashboard in your browser.

You'll see a lot of text scroll by. That's normal. When it finishes you'll see **"Install complete"** and your browser will open.

Total time: about 3–5 minutes on a normal connection.

---

## 3. After install

You're done installing. **Three** things to do before first use:

1. **Restart Claude Desktop.** Right-click its tray icon → Quit. Reopen it. (This makes Claude pick up the new tools.) To check it worked: in Claude Desktop, open Settings → Developer → MCP. You should see `audio_transcriber` listed.

2. **Open the dashboard.** Look for the **Audio Transcriber** shortcut on your desktop. Double-click it. Browser opens to http://127.0.0.1:8765/

3. **Add your OpenAI key.** In the dashboard, click **Settings** in the top nav. Paste the OpenAI key we sent you, click **Save**.

That's it — you're ready.

## 4. How to use it

Audio Transcriber captures meetings automatically. When you want to read summaries and action items, you have two options:

- **Open the dashboard** (desktop shortcut) — shows recent meetings, action items, decisions.
- **Ask Claude Desktop** — open Claude Desktop and say things like:
  - "List pending meetings and synthesize them." → Claude reads the raw transcripts and pulls out the title, summary, action items, decisions.
  - "What are my open action items?" → Claude reads your action-item table.
  - "What did we decide about Buildertrend?" → Claude searches your decisions.

You can also tell **Claude Code** (separately):
- "Start transcribing my meeting." → Recording begins.
- "Stop transcribing." → Saves and queues for synthesis.

---

## 5. If something goes wrong

Three issues come up occasionally. Each has a one-line fix you can paste into PowerShell.

### "Python is not recognized" or "Python not found"

The installer tries to grab Python automatically, but on some locked-down PCs it can't. Install it yourself:

```powershell
winget install Python.Python.3.12
```

Close PowerShell, reopen it, and run the install command from Step 1 again.

### "OneDrive folder not found" or transcripts aren't syncing

Make sure OneDrive is running and signed in. Click the cloud icon in your taskbar (bottom-right, near the clock). If it says **"Sign in"**, sign in with your work email. Then re-run the install command.

### "Running scripts is disabled on this system" or "execution of scripts is disabled"

Your PC is blocking PowerShell scripts. Run this one line, then try the install again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
```

This only affects your user account — nothing system-wide, no admin needed.

---

**Still stuck?** Email Tyler at tyler@agentconsult.ai with a screenshot of the PowerShell window and we'll get you running.
