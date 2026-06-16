"""CLI entry point. Invoked by Claude Code on the CEO's laptop, and by
the scheduled tasks that drive the auto-record loop + Graph poller.

All commands are designed to be safe to call from a non-interactive context
(no prompts, no stdin reads). Output goes to stdout as plain text.
"""
import argparse
import json
import os
import sys

from audio_transcriber.config import load_config


def cmd_meeting(args, cfg):
    from audio_transcriber.capture import meeting
    if args.sub == "start":
        result = meeting.start(cfg, app_hint=args.app)
        if result["ok"]:
            print(f"Recording started → {result['audio_path']}")
        else:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            sys.exit(1)
    elif args.sub == "stop":
        result = meeting.stop(cfg)
        if result["ok"]:
            print(f"Saved meeting → {result['saved_to']} ({result['duration_seconds']}s)")
        else:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            sys.exit(1)
    elif args.sub == "status":
        s = meeting.status(cfg)
        if s["active"]:
            print(f"ACTIVE since {s['started_at']} ({s.get('app_hint', '?')})")
        else:
            print("idle")


def cmd_ingest(args, cfg):
    if args.sub == "vtt":
        from audio_transcriber.ingest.vtt_ingest import ingest_vtt
        path = ingest_vtt(args.path, cfg)
        print(f"Saved → {path}")
    elif args.sub == "teams-paste":
        from audio_transcriber.ingest.teams_paste_ingest import ingest_teams_paste
        path = ingest_teams_paste(args.path, cfg)
        print(f"Saved → {path}")
    elif args.sub == "audio":
        from audio_transcriber.transcribe.router import transcribe_and_save
        path = transcribe_and_save(
            audio_path=args.path,
            cfg=cfg,
            source="whisper_dropzone",
        )
        print(f"Saved → {path}")


def cmd_devices(args, cfg):
    """List mic + loopback audio devices on this machine (run first on new hardware)."""
    from audio_transcriber.capture.audio_devices import print_devices
    print_devices()


def cmd_record_test(args, cfg):
    """Record a few seconds of mic+loopback and report per-channel signal levels."""
    import time
    from audio_transcriber.capture.wasapi_recorder import DualStreamRecorder, new_recording_path
    from audio_transcriber.config import get_local_dir

    out = args.out or new_recording_path(get_local_dir(cfg))
    rec = DualStreamRecorder(out, cfg)
    print(f"Recording {args.seconds}s → {out}")
    print("Talk into the mic AND play some audio (or be in a call) so both channels get signal...")
    rec.start()
    time.sleep(args.seconds)
    rec.stop()
    lv = rec.levels
    print(f"\nChannels written: {lv['channels']}")
    print(f"  LEFT  (mic / owner)  RMS: {lv['left_rms']:.4f}  {'OK' if lv['left_rms'] > 0.001 else '← SILENT'}")
    print(f"  RIGHT (loopback/them) RMS: {lv['right_rms']:.4f}  {'OK' if lv['right_rms'] > 0.001 else '← SILENT'}")
    print(f"\nSaved: {out}")
    print("Next: python -m audio_transcriber transcribe-local \"%s\"" % out)


def cmd_transcribe_local(args, cfg):
    """On-device transcription test — prints utterances, no API key, no save."""
    from audio_transcriber.transcribe.whisper_local import transcribe_auto
    from audio_transcriber.ingest.vtt_parser import utterances_to_plain_text
    utterances, has_speakers, participants = transcribe_auto(args.path, cfg)
    print(f"speakers={has_speakers}  participants={participants}  utterances={len(utterances)}\n")
    print(utterances_to_plain_text(utterances) or "(empty transcript)")


def cmd_stage_model(args, cfg):
    """Download a faster-whisper model snapshot for offline use on a firewalled box.

    Run this on a machine WITH internet (e.g. the Mac), then copy --out to the
    target laptop and set transcribe.model_dir to that path.
    """
    from huggingface_hub import snapshot_download
    from audio_transcriber.transcribe.whisper_local import MODEL_REPOS
    repo = MODEL_REPOS.get(args.model, args.model)
    print(f"Downloading {repo} → {args.out}")
    path = snapshot_download(repo_id=repo, local_dir=args.out)
    print(f"Done. Copy this folder to the target machine, then set in config.json:")
    print(f'  "transcribe": {{ "model_dir": "<path-on-target>" }}')
    print(f"Staged at: {path}")


def cmd_graph_poll(args, cfg):
    from audio_transcriber.capture.graph_poller import poll_once
    count = poll_once(cfg, lookback_days=args.lookback)
    print(f"Ingested {count} new Teams meeting{'s' if count != 1 else ''}.")


def cmd_graph_auth(args, cfg):
    from audio_transcriber.capture.graph_auth import run_device_code_flow
    scopes = cfg.get("graph", {}).get("scopes", [])
    run_device_code_flow(args.client_id, args.tenant_id, scopes)
    print("Graph authentication complete. Refresh token saved to Credential Manager.")


def cmd_transcript(args, cfg):
    from audio_transcriber.storage.index import load_index
    from audio_transcriber.storage.manager import search_transcripts
    if args.sub == "list":
        idx = load_index(cfg)
        for m in idx["meetings"][-args.limit:]:
            print(f"{m['date']}  {m['id']}  {m['title']}")
    elif args.sub == "search":
        for r in search_transcripts(args.query, cfg):
            print(f"{r['date']}  {r['title']}\n  {r['snippet']}\n")


def cmd_digest(args, cfg):
    from audio_transcriber.digest import pipeline, queries
    if args.sub == "status":
        s = queries.get_digest_status(cfg)
        for k, v in s.items():
            print(f"  {k}: {v}")
    elif args.sub == "run":
        pipeline.digest_all_unprocessed(cfg)
    elif args.sub == "rebuild":
        pipeline.rebuild_digest(cfg)
    elif args.sub == "tasks":
        rows = queries.get_overdue_tasks(cfg) if args.overdue else queries.get_open_tasks(cfg, owner=args.owner)
        for r in rows:
            due = f" (due {r['due_date']})" if r.get("due_date") else ""
            print(f"  [{r['id']}] {r.get('owner') or '(unattributed)'}: {r['task']}{due}")
    elif args.sub == "decisions":
        for r in queries.get_decisions(cfg, since=args.since):
            print(f"  {r['decided_at']}  {r['decision']}")
    elif args.sub == "person":
        person = queries.get_person_context(cfg, args.name)
        if not person:
            print(f"No record for {args.name}")
            return
        print(f"{person['name']}: {person.get('meeting_count', 0)} meetings, last on {person.get('last_meeting_date')}")
        print(f"  Topics: {', '.join(person.get('topics_discussed') or [])}")
        print(f"  Open tasks: {len(person.get('open_tasks', []))}")
    elif args.sub == "topics":
        for t in queries.get_topics(cfg):
            print(f"  {t}")


def cmd_set_key(args, cfg):
    from audio_transcriber.auth import credentials
    key_map = {
        "anthropic": "anthropic_api_key",
        "openai": "openai_api_key",
    }
    name = key_map.get(args.provider, args.provider)
    credentials.set_secret(name, args.value)
    print(f"Saved {name} to Credential Manager.")


def cmd_synthesize_pending(args, cfg):
    """Synthesize pending meetings via the Anthropic API fallback path.

    Primary synthesis happens through Claude Desktop (driven by the MCP server).
    This is the failsafe — invoke it when Claude Desktop isn't around, or wire
    it into a scheduled task for guaranteed forward progress.
    """
    from audio_transcriber.synthesize.pending import list_pending, run_api_fallback
    pending = list_pending(cfg)
    if not pending:
        print("No pending meetings.")
        return
    print(f"{len(pending)} pending meeting(s).")
    if args.dry_run:
        for p in pending:
            print(f"  {p['id']}  {p['date']}  {p.get('title','')}")
        return
    result = run_api_fallback(cfg, meeting_ids=args.id if args.id else None)
    print(f"Processed: {result['processed']}  Skipped: {result['skipped']}  Errors: {len(result['errors'])}")
    for e in result["errors"]:
        print(f"  ! {e['meeting_id']}: {e['error']}")


def cmd_mcp_server(args, cfg):
    """Run the MCP server in the foreground (stdio). Claude Desktop launches this."""
    from audio_transcriber.mcp_server import main as run_mcp
    run_mcp()


def cmd_claude_config(args, cfg):
    """Write/merge the audio_transcriber entry into claude_desktop_config.json.

    Detects Claude Desktop's config path on Windows (%APPDATA%\\Claude\\) or
    macOS (~/Library/Application Support/Claude/). Preserves any other MCP
    servers already configured.
    """
    import sys as _sys
    from pathlib import Path

    if _sys.platform.startswith("win"):
        config_dir = Path(os.environ.get("APPDATA", "")) / "Claude"
    elif _sys.platform == "darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "Claude"
    else:
        config_dir = Path.home() / ".config" / "Claude"

    config_path = config_dir / "claude_desktop_config.json"
    config_dir.mkdir(parents=True, exist_ok=True)

    existing = {}
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
        except json.JSONDecodeError:
            print(f"WARN: {config_path} is not valid JSON. Aborting to avoid clobbering it.", file=_sys.stderr)
            sys.exit(1)

    # Resolve the python executable that runs the MCP server. Default: this
    # interpreter (set by the venv when installer/install.ps1 runs us).
    python_exe = args.python_exe or _sys.executable
    existing.setdefault("mcpServers", {})
    existing["mcpServers"]["audio_transcriber"] = {
        "command": python_exe,
        "args": ["-m", "audio_transcriber.mcp_server"],
    }

    config_path.write_text(json.dumps(existing, indent=2))
    print(f"Wrote MCP entry to {config_path}")
    print("Restart Claude Desktop to pick up the change.")


def main():
    parser = argparse.ArgumentParser(prog="audio_transcriber")
    sub = parser.add_subparsers(dest="cmd", required=True)

    mt = sub.add_parser("meeting", help="Record meetings via WASAPI loopback")
    mt_sub = mt.add_subparsers(dest="sub", required=True)
    mt_start = mt_sub.add_parser("start", help="Start a manual recording")
    mt_start.add_argument("--app", default=None, help="App hint (zoom, teams, etc.)")
    mt_sub.add_parser("stop", help="Stop the active recording and process it")
    mt_sub.add_parser("status", help="Show recording state")

    ig = sub.add_parser("ingest", help="Import transcripts/audio from external sources")
    ig_sub = ig.add_subparsers(dest="sub", required=True)
    ig_vtt = ig_sub.add_parser("vtt", help="Import a .vtt transcript (Teams)")
    ig_vtt.add_argument("path")
    ig_tp = ig_sub.add_parser("teams-paste", help="Import a copy-pasted Teams transcript")
    ig_tp.add_argument("path")
    ig_a = ig_sub.add_parser("audio", help="Transcribe a dropped audio/video file via Whisper")
    ig_a.add_argument("path")

    sub.add_parser("devices", help="List mic + loopback audio devices (run first on new hardware)")

    rt = sub.add_parser("record-test", help="Record a few seconds of mic+loopback and report levels")
    rt.add_argument("--seconds", type=int, default=15)
    rt.add_argument("--out", default=None, help="Output WAV path (default: recordings dir)")

    tl = sub.add_parser("transcribe-local", help="On-device transcribe a WAV (no key, no save)")
    tl.add_argument("path")

    sm = sub.add_parser("stage-model", help="Download a faster-whisper model for offline use")
    sm.add_argument("--model", default="small.en", help="tiny.en|base.en|small.en|medium.en|large-v3")
    sm.add_argument("--out", required=True, help="Target folder for the model snapshot")

    gp = sub.add_parser("graph-poll", help="One Graph poll for new Teams transcripts")
    gp.add_argument("--lookback", type=int, default=7)

    ga = sub.add_parser("graph-auth", help="One-shot Graph OAuth device-code flow")
    ga.add_argument("--client-id", required=True)
    ga.add_argument("--tenant-id", required=True)

    tr = sub.add_parser("transcript", help="Browse stored meetings")
    tr_sub = tr.add_subparsers(dest="sub", required=True)
    tr_l = tr_sub.add_parser("list")
    tr_l.add_argument("--limit", type=int, default=20)
    tr_s = tr_sub.add_parser("search")
    tr_s.add_argument("query")

    dg = sub.add_parser("digest", help="Query digest tables")
    dg_sub = dg.add_subparsers(dest="sub", required=True)
    dg_sub.add_parser("status")
    dg_sub.add_parser("run")
    dg_sub.add_parser("rebuild")
    dg_t = dg_sub.add_parser("tasks")
    dg_t.add_argument("--owner", default=None)
    dg_t.add_argument("--overdue", action="store_true")
    dg_d = dg_sub.add_parser("decisions")
    dg_d.add_argument("--since", default=None)
    dg_p = dg_sub.add_parser("person")
    dg_p.add_argument("name")
    dg_sub.add_parser("topics")

    sk = sub.add_parser("set-key", help="Save an API key to Credential Manager")
    sk.add_argument("provider", choices=["anthropic", "openai"])
    sk.add_argument("value")

    sp = sub.add_parser("synthesize-pending", help="Synthesize queued meetings via Anthropic API (fallback path)")
    sp.add_argument("--dry-run", action="store_true", help="Just list what would be processed")
    sp.add_argument("--id", nargs="*", help="Specific meeting IDs to process (default: all pending)")

    sub.add_parser("mcp-server", help="Run the MCP server (stdio). Claude Desktop launches this.")

    cc = sub.add_parser("claude-config", help="Write/merge audio_transcriber into claude_desktop_config.json")
    cc.add_argument("--python-exe", default=None, help="Override python.exe path (default: this interpreter)")

    args = parser.parse_args()
    cfg = load_config()

    dispatch = {
        "meeting": cmd_meeting,
        "ingest": cmd_ingest,
        "devices": cmd_devices,
        "record-test": cmd_record_test,
        "transcribe-local": cmd_transcribe_local,
        "stage-model": cmd_stage_model,
        "graph-poll": cmd_graph_poll,
        "graph-auth": cmd_graph_auth,
        "transcript": cmd_transcript,
        "digest": cmd_digest,
        "set-key": cmd_set_key,
        "synthesize-pending": cmd_synthesize_pending,
        "mcp-server": cmd_mcp_server,
        "claude-config": cmd_claude_config,
    }
    dispatch[args.cmd](args, cfg)


if __name__ == "__main__":
    main()
