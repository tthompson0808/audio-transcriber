"""Read-only query API for downstream agents (notification, email-drafter, etc.)."""
import json
from datetime import datetime, timedelta, timezone

from audio_transcriber.digest.db import DIGEST_VERSION, get_connection, init_db
from audio_transcriber.storage.index import load_index


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# --- Tasks ---

def get_open_tasks(cfg: dict, owner: str = None, since: str = None) -> list[dict]:
    init_db(cfg)
    conn = get_connection(cfg)
    query = "SELECT * FROM tasks WHERE status = 'open'"
    params = []
    if owner:
        query += " AND owner LIKE ?"
        params.append(f"%{owner}%")
    if since:
        query += " AND created_at >= ?"
        params.append(since)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def get_overdue_tasks(cfg: dict) -> list[dict]:
    init_db(cfg)
    conn = get_connection(cfg)
    today = datetime.now().strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'open' AND due_date IS NOT NULL AND due_date < ? ORDER BY due_date",
        (today,),
    ).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def get_completed_tasks(cfg: dict, owner: str = None, since: str = None) -> list[dict]:
    init_db(cfg)
    conn = get_connection(cfg)
    query = "SELECT * FROM tasks WHERE status = 'completed'"
    params = []
    if owner:
        query += " AND owner LIKE ?"
        params.append(f"%{owner}%")
    if since:
        query += " AND completed_at >= ?"
        params.append(since)
    query += " ORDER BY completed_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def complete_task(cfg: dict, task_id: int) -> None:
    init_db(cfg)
    conn = get_connection(cfg)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?", (now, task_id))
    row = conn.execute("SELECT owner FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row and row["owner"]:
        _refresh_task_summary_internal(conn, row["owner"])
    conn.commit()
    conn.close()


def cancel_task(cfg: dict, task_id: int) -> None:
    init_db(cfg)
    conn = get_connection(cfg)
    conn.execute("UPDATE tasks SET status = 'cancelled' WHERE id = ?", (task_id,))
    row = conn.execute("SELECT owner FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row and row["owner"]:
        _refresh_task_summary_internal(conn, row["owner"])
    conn.commit()
    conn.close()


def get_stale_tasks(cfg: dict, days: int = 7) -> list[dict]:
    init_db(cfg)
    conn = get_connection(cfg)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'open' AND due_date IS NULL AND created_at < ? ORDER BY created_at",
        (cutoff,),
    ).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def archive_old_completed(cfg: dict, days: int = 30) -> int:
    init_db(cfg)
    conn = get_connection(cfg)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc).isoformat()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status = 'completed' AND completed_at < ?", (cutoff,)
    ).fetchall()
    for row in rows:
        conn.execute(
            """INSERT INTO tasks_archive (id, meeting_id, owner, task, due_date, status, created_at, completed_at, archived_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["id"], row["meeting_id"], row["owner"], row["task"], row["due_date"],
             row["status"], row["created_at"], row["completed_at"], now),
        )
        conn.execute("DELETE FROM tasks WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return len(rows)


# --- Decisions ---

def get_decisions(cfg: dict, meeting_id: str = None, since: str = None, keyword: str = None) -> list[dict]:
    init_db(cfg)
    conn = get_connection(cfg)
    query = "SELECT * FROM decisions WHERE 1=1"
    params = []
    if meeting_id:
        query += " AND meeting_id = ?"
        params.append(meeting_id)
    if since:
        query += " AND decided_at >= ?"
        params.append(since)
    if keyword:
        query += " AND (decision LIKE ? OR context LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    query += " ORDER BY decided_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    results = _rows_to_dicts(rows)
    for r in results:
        if r.get("participants"):
            r["participants"] = json.loads(r["participants"])
    return results


# --- People ---

def get_person_context(cfg: dict, name: str) -> dict | None:
    init_db(cfg)
    conn = get_connection(cfg)
    row = conn.execute("SELECT * FROM people WHERE name LIKE ?", (f"%{name}%",)).fetchone()
    if not row:
        conn.close()
        return None
    person = dict(row)
    if person.get("topics_discussed"):
        person["topics_discussed"] = json.loads(person["topics_discussed"])
    person["open_tasks"] = _rows_to_dicts(
        conn.execute("SELECT * FROM tasks WHERE owner LIKE ? AND status = 'open'", (f"%{name}%",)).fetchall()
    )
    person["recent_decisions"] = _rows_to_dicts(
        conn.execute(
            "SELECT * FROM decisions WHERE participants LIKE ? ORDER BY decided_at DESC LIMIT 5",
            (f"%{name}%",),
        ).fetchall()
    )
    conn.close()
    return person


def get_all_people(cfg: dict) -> list[dict]:
    init_db(cfg)
    conn = get_connection(cfg)
    rows = conn.execute("SELECT * FROM people ORDER BY last_meeting_date DESC").fetchall()
    conn.close()
    results = _rows_to_dicts(rows)
    for r in results:
        if r.get("topics_discussed"):
            r["topics_discussed"] = json.loads(r["topics_discussed"])
    return results


# --- Topics ---

def get_meetings_by_topic(cfg: dict, topic: str) -> list[dict]:
    init_db(cfg)
    conn = get_connection(cfg)
    rows = conn.execute(
        """SELECT t.topic, t.meeting_id, d.meeting_id as dm, d.digested_at
           FROM topics t LEFT JOIN digest_log d ON t.meeting_id = d.meeting_id
           WHERE t.topic LIKE ? ORDER BY t.meeting_id DESC""",
        (f"%{topic}%",),
    ).fetchall()
    conn.close()
    return _rows_to_dicts(rows)


def get_topics(cfg: dict, meeting_id: str = None) -> list[str]:
    init_db(cfg)
    conn = get_connection(cfg)
    if meeting_id:
        rows = conn.execute("SELECT DISTINCT topic FROM topics WHERE meeting_id = ?", (meeting_id,)).fetchall()
    else:
        rows = conn.execute("SELECT DISTINCT topic FROM topics ORDER BY topic").fetchall()
    conn.close()
    return [r["topic"] for r in rows]


# --- Maintenance ---

def get_undigested_meetings(cfg: dict) -> list[str]:
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
    return [m["id"] for m in index["meetings"] if m["id"] not in digested]


def get_digest_status(cfg: dict) -> dict:
    init_db(cfg)
    index = load_index(cfg)
    conn = get_connection(cfg)
    total = len(index["meetings"])
    digested = conn.execute("SELECT COUNT(*) FROM digest_log").fetchone()[0]
    open_tasks = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'open'").fetchone()[0]
    total_decisions = conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
    total_people = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    total_topics = conn.execute("SELECT COUNT(DISTINCT topic) FROM topics").fetchone()[0]
    conn.close()
    return {
        "total_meetings": total,
        "digested": digested,
        "pending": total - digested,
        "open_tasks": open_tasks,
        "decisions": total_decisions,
        "people": total_people,
        "topics": total_topics,
    }


# --- Internal helpers ---

def _refresh_task_summary_internal(conn, name: str) -> None:
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
