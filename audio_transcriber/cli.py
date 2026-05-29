"""CLI entry point. Invoked by Claude Code on the CEO's laptop, and by
the scheduled tasks that drive the auto-record loop + Graph poller.

All commands are designed to be safe to call from a non-interactive context
(no prompts, no stdin reads). Output goes to stdout as plain text.
"""
import argparse
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

    args = parser.parse_args()
    cfg = load_config()

    dispatch = {
        "meeting": cmd_meeting,
        "ingest": cmd_ingest,
        "graph-poll": cmd_graph_poll,
        "graph-auth": cmd_graph_auth,
        "transcript": cmd_transcript,
        "digest": cmd_digest,
        "set-key": cmd_set_key,
    }
    dispatch[args.cmd](args, cfg)


if __name__ == "__main__":
    main()
