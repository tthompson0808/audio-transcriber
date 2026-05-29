"""Extract structured tasks/decisions/topics/people from each meeting."""
import json
import os
from datetime import datetime, timezone

from audio_transcriber.claude_api import get_client
from audio_transcriber.config import get_data_dir
from audio_transcriber.digest.db import DIGEST_VERSION, get_connection, init_db
from audio_transcriber.storage.index import load_index


EXTRACTION_PROMPT = """You analyze meeting transcripts and extract structured data. Given a meeting transcript, return a JSON object with exactly these keys:

- "tasks": array of objects with {"owner": "Person name or null", "task": "What they need to do", "due": "YYYY-MM-DD or null"}. Look for both explicit commitments ("I'll send that by Friday") and implicit ones ("we should follow up on X"). Only include actionable items, not discussion points. If the speaker says "I'll" or "I will", the owner is that speaker. If no clear action items exist, return empty array. If the transcript has no speaker labels, set owner to "(unattributed)" when context doesn't make it obvious.

- "decisions": array of objects with {"decision": "What was decided", "context": "Brief explanation of why or what led to this"}. Look for conclusions, agreements, choices made — even informal ones like "so we're going with X then". If no clear decisions, return empty array.

- "topics": array of lowercase hyphenated topic slugs (2-4 words max) that describe the main subjects discussed. Examples: "claude-pricing", "business-expenses", "buildertrend-api". Aim for 2-5 topics per meeting. Be consistent — use the same slug if the same topic comes up in different meetings.

Return ONLY valid JSON. No markdown fencing."""


def _extract_from_meeting(meeting: dict, cfg: dict) -> dict:
    client = get_client(cfg)

    content = f"Meeting: {meeting['title']} — {meeting['date']}\n"
    content += f"Participants: {', '.join(meeting.get('participants', []))}\n\n"
    if meeting.get("summary"):
        content += f"Summary: {meeting['summary']}\n\n"
    content += "Transcript:\n"
    for u in meeting.get("utterances", []):
        ts = f"[{u['start']}] " if u.get("start") else ""
        speaker = u.get("speaker", "Unknown")
        content += f"{ts}{speaker}: {u['text']}\n"

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=EXTRACTION_PROMPT,
        messages=[{"role": "user", "content": content}],
    )
    return json.loads(response.content[0].text)


def _update_person(conn, name: str, meeting_id: str, meeting_date: str, new_topics: list[str]) -> None:
    row = conn.execute("SELECT * FROM people WHERE name = ?", (name,)).fetchone()

    if row:
        existing_topics = json.loads(row["topics_discussed"] or "[]")
        merged = list(dict.fromkeys(new_topics + existing_topics))
        conn.execute(
            """UPDATE people SET last_meeting_id = ?, last_meeting_date = ?,
               meeting_count = meeting_count + 1, topics_discussed = ?
               WHERE name = ?""",
            (meeting_id, meeting_date, json.dumps(merged), name),
        )
    else:
        conn.execute(
            """INSERT INTO people (name, last_meeting_id, last_meeting_date, meeting_count, topics_discussed)
               VALUES (?, ?, ?, 1, ?)""",
            (name, meeting_id, meeting_date, json.dumps(new_topics)),
        )


def _refresh_task_summary(conn, name: str) -> None:
    rows = conn.execute(
        "SELECT task FROM tasks WHERE owner = ? AND status = 'open' ORDER BY id DESC LIMIT 3",
        (name,),
    ).fetchall()
    count = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE owner = ? AND status = 'open'", (name,)
    ).fetchone()[0]

    if count == 0:
        summary = "No open tasks"
    else:
        latest = rows[0]["task"][:60]
        summary = f"{count} open task{'s' if count != 1 else ''}, latest: {latest}"

    conn.execute("UPDATE people SET open_task_summary = ? WHERE name = ?", (summary, name))


def digest_meeting(meeting_id: str, cfg: dict) -> bool:
    init_db(cfg)
    conn = get_connection(cfg)

    existing = conn.execute(
        "SELECT digest_version FROM digest_log WHERE meeting_id = ?", (meeting_id,)
    ).fetchone()
    if existing and existing["digest_version"] >= DIGEST_VERSION:
        conn.close()
        return False

    index = load_index(cfg)
    entry = next((m for m in index["meetings"] if m["id"] == meeting_id), None)
    if not entry:
        conn.close()
        raise ValueError(f"Meeting {meeting_id} not found in index")

    meeting_path = os.path.join(get_data_dir(cfg), "meetings", entry["path"])
    with open(meeting_path) as f:
        meeting = json.load(f)

    print(f"Digesting: {meeting['title']} ({meeting_id})...")
    try:
        extracted = _extract_from_meeting(meeting, cfg)
    except Exception as e:
        print(f"Extraction failed: {e}")
        conn.close()
        return False

    meeting_date = meeting["date"]
    participants_json = json.dumps(meeting.get("participants", []))
    topic_slugs = extracted.get("topics", [])

    if existing:
        conn.execute("DELETE FROM tasks WHERE meeting_id = ? AND status = 'open'", (meeting_id,))
        conn.execute("DELETE FROM decisions WHERE meeting_id = ?", (meeting_id,))
        conn.execute("DELETE FROM topics WHERE meeting_id = ?", (meeting_id,))

    for t in extracted.get("tasks", []):
        conn.execute(
            "INSERT INTO tasks (meeting_id, owner, task, due_date, status, created_at) VALUES (?, ?, ?, ?, 'open', ?)",
            (meeting_id, t.get("owner"), t["task"], t.get("due"), meeting_date),
        )

    for d in extracted.get("decisions", []):
        conn.execute(
            "INSERT INTO decisions (meeting_id, decision, context, participants, decided_at) VALUES (?, ?, ?, ?, ?)",
            (meeting_id, d["decision"], d.get("context"), participants_json, meeting_date),
        )

    for topic in topic_slugs:
        conn.execute(
            "INSERT INTO topics (meeting_id, topic) VALUES (?, ?)",
            (meeting_id, topic.lower().strip()),
        )

    for name in meeting.get("participants", []):
        _update_person(conn, name, meeting_id, meeting_date, topic_slugs)
        _refresh_task_summary(conn, name)

    conn.execute(
        "INSERT OR REPLACE INTO digest_log (meeting_id, digested_at, digest_version) VALUES (?, ?, ?)",
        (meeting_id, datetime.now(timezone.utc).isoformat(), DIGEST_VERSION),
    )

    conn.commit()
    conn.close()
    print(f"  → {len(extracted.get('tasks', []))} tasks, {len(extracted.get('decisions', []))} decisions, {len(topic_slugs)} topics")
    return True


def digest_all_unprocessed(cfg: dict) -> int:
    init_db(cfg)
    index = load_index(cfg)
    conn = get_connection(cfg)

    digested = {
        row["meeting_id"]
        for row in conn.execute(
            "SELECT meeting_id FROM digest_log WHERE digest_version >= ?", (DIGEST_VERSION,)
        ).fetchall()
    }
    conn.close()

    pending = [m for m in index["meetings"] if m["id"] not in digested]
    if not pending:
        print("All meetings already digested.")
        return 0

    count = 0
    for m in pending:
        if digest_meeting(m["id"], cfg):
            count += 1

    print(f"Digested {count} meeting{'s' if count != 1 else ''}.")
    return count


def rebuild_digest(cfg: dict) -> int:
    from audio_transcriber.digest.db import reset_db
    print("Rebuilding digest from scratch...")
    reset_db(cfg)
    index = load_index(cfg)
    count = 0
    for m in index["meetings"]:
        if digest_meeting(m["id"], cfg):
            count += 1
    print(f"Rebuild complete: {count} meeting{'s' if count != 1 else ''} digested.")
    return count
