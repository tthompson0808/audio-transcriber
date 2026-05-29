"""Pending-synthesis queue.

The queue is implicit: any meeting JSON with `synthesized: false` is pending.
This module enumerates the queue, applies a synthesis result, and offers an
Anthropic API fallback runner for cases where Claude Desktop isn't available.

Primary synthesis path is the MCP server (audio_transcriber.mcp_server), which
Claude Desktop drives. This module is the fallback + the routine entry point.
"""
import json
import os
from datetime import datetime, timezone

from audio_transcriber.config import get_data_dir
from audio_transcriber.storage.index import load_index


def list_pending(cfg: dict) -> list[dict]:
    """Return index entries for meetings where the JSON has `synthesized: false`."""
    idx = load_index(cfg)
    data_dir = get_data_dir(cfg)
    pending = []
    for entry in idx["meetings"]:
        path = os.path.join(data_dir, "meetings", entry["path"])
        if not os.path.exists(path):
            continue
        try:
            with open(path) as f:
                meeting = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not meeting.get("synthesized", False):
            pending.append({**entry, "_path": path, "has_speakers": meeting.get("has_speakers", True)})
    return pending


def load_meeting(cfg: dict, meeting_id: str) -> dict | None:
    idx = load_index(cfg)
    entry = next((m for m in idx["meetings"] if m["id"] == meeting_id), None)
    if not entry:
        return None
    path = os.path.join(get_data_dir(cfg), "meetings", entry["path"])
    if not os.path.exists(path):
        return None
    with open(path) as f:
        meeting = json.load(f)
    meeting["_path"] = path
    return meeting


def apply_synthesis(
    cfg: dict,
    meeting_id: str,
    title: str,
    summary: str,
    action_items: list[dict],
    decisions: list[dict],
    topics: list[str],
    synthesized_by: str,
) -> dict:
    """Persist a synthesis result. Updates meeting JSON, populates digest tables.

    `synthesized_by` is "claude_desktop" or "api_fallback" — informational only.
    """
    meeting = load_meeting(cfg, meeting_id)
    if not meeting:
        raise ValueError(f"Meeting {meeting_id} not found")

    path = meeting.pop("_path")

    meeting["title"] = title or meeting.get("title", "Untitled")
    meeting["summary"] = summary
    meeting["action_items"] = action_items
    meeting["synthesized"] = True
    meeting["synthesized_at"] = datetime.now(timezone.utc).isoformat()
    meeting["synthesized_by"] = synthesized_by

    with open(path, "w") as f:
        json.dump(meeting, f, indent=2)

    _write_digest_rows(cfg, meeting_id, meeting, action_items, decisions, topics)

    return {"meeting_id": meeting_id, "synthesized_by": synthesized_by, "tasks": len(action_items), "decisions": len(decisions), "topics": len(topics)}


def _write_digest_rows(cfg, meeting_id, meeting, action_items, decisions, topics):
    """Insert into tasks/decisions/topics/people tables. Replaces existing rows for the meeting."""
    from audio_transcriber.digest.db import DIGEST_VERSION, get_connection, init_db

    init_db(cfg)
    conn = get_connection(cfg)

    conn.execute("DELETE FROM tasks WHERE meeting_id = ? AND status = 'open'", (meeting_id,))
    conn.execute("DELETE FROM decisions WHERE meeting_id = ?", (meeting_id,))
    conn.execute("DELETE FROM topics WHERE meeting_id = ?", (meeting_id,))

    meeting_date = meeting["date"]
    participants_json = json.dumps(meeting.get("participants", []))

    for t in action_items:
        conn.execute(
            "INSERT INTO tasks (meeting_id, owner, task, due_date, status, created_at) VALUES (?, ?, ?, ?, 'open', ?)",
            (meeting_id, t.get("owner"), t["task"], t.get("due") or t.get("due_date"), meeting_date),
        )

    for d in decisions:
        conn.execute(
            "INSERT INTO decisions (meeting_id, decision, context, participants, decided_at) VALUES (?, ?, ?, ?, ?)",
            (meeting_id, d["decision"], d.get("context"), participants_json, meeting_date),
        )

    for topic in topics:
        conn.execute(
            "INSERT INTO topics (meeting_id, topic) VALUES (?, ?)",
            (meeting_id, topic.lower().strip()),
        )

    for name in meeting.get("participants", []):
        row = conn.execute("SELECT * FROM people WHERE name = ?", (name,)).fetchone()
        if row:
            existing_topics = json.loads(row["topics_discussed"] or "[]")
            merged = list(dict.fromkeys(topics + existing_topics))
            conn.execute(
                "UPDATE people SET last_meeting_id = ?, last_meeting_date = ?, meeting_count = meeting_count + 1, topics_discussed = ? WHERE name = ?",
                (meeting_id, meeting_date, json.dumps(merged), name),
            )
        else:
            conn.execute(
                "INSERT INTO people (name, last_meeting_id, last_meeting_date, meeting_count, topics_discussed) VALUES (?, ?, ?, 1, ?)",
                (name, meeting_id, meeting_date, json.dumps(topics)),
            )

    conn.execute(
        "INSERT OR REPLACE INTO digest_log (meeting_id, digested_at, digest_version) VALUES (?, ?, ?)",
        (meeting_id, datetime.now(timezone.utc).isoformat(), DIGEST_VERSION),
    )

    conn.commit()
    conn.close()


def run_api_fallback(cfg: dict, meeting_ids: list[str] | None = None) -> dict:
    """Synthesize pending meetings via the Anthropic API. Used as fallback when
    Claude Desktop hasn't picked them up (e.g. tray-side scheduled task, or
    the 3x-daily routine if it's configured to never block).

    Returns {processed, skipped, errors}.
    """
    from audio_transcriber.synthesize.claude import summarize_transcript
    from audio_transcriber.ingest.vtt_parser import utterances_to_plain_text

    targets = list_pending(cfg) if meeting_ids is None else [
        load_meeting(cfg, mid) for mid in meeting_ids if load_meeting(cfg, mid)
    ]

    processed = 0
    skipped = 0
    errors = []

    for entry in targets:
        meeting_id = entry["id"]
        meeting = entry if "utterances" in entry else load_meeting(cfg, meeting_id)
        if not meeting:
            skipped += 1
            continue

        text = utterances_to_plain_text(meeting.get("utterances", []))
        if not text.strip():
            skipped += 1
            continue

        try:
            synth = summarize_transcript(text, cfg, has_speakers=meeting.get("has_speakers", True))
        except Exception as e:
            errors.append({"meeting_id": meeting_id, "error": str(e)})
            continue

        try:
            extracted = _extract_digest_via_api(meeting, synth, cfg)
        except Exception as e:
            errors.append({"meeting_id": meeting_id, "error": f"digest extraction: {e}"})
            extracted = {"decisions": [], "topics": []}

        apply_synthesis(
            cfg,
            meeting_id=meeting_id,
            title=synth.get("title", meeting.get("title")),
            summary=synth.get("summary", ""),
            action_items=synth.get("action_items", []),
            decisions=extracted.get("decisions", []),
            topics=extracted.get("topics", []),
            synthesized_by="api_fallback",
        )
        processed += 1

    return {"processed": processed, "skipped": skipped, "errors": errors}


def _extract_digest_via_api(meeting: dict, synth: dict, cfg: dict) -> dict:
    """Use the existing digest extraction prompt to pull decisions + topics."""
    from audio_transcriber.claude_api import get_client
    from audio_transcriber.digest.pipeline import EXTRACTION_PROMPT

    client = get_client(cfg)
    content = f"Meeting: {synth.get('title', meeting.get('title', 'Untitled'))} — {meeting['date']}\n"
    content += f"Participants: {', '.join(meeting.get('participants', []))}\n\n"
    if synth.get("summary"):
        content += f"Summary: {synth['summary']}\n\n"
    content += "Transcript:\n"
    for u in meeting.get("utterances", []):
        ts = f"[{u['start']}] " if u.get("start") else ""
        content += f"{ts}{u.get('speaker', 'Unknown')}: {u['text']}\n"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=EXTRACTION_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return json.loads(response.content[0].text)
