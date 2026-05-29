"""SQLite digest DB. Schema is column-identical to Tyler's AudioTools digest.db."""
import os
import sqlite3

from audio_transcriber.config import get_local_dir

DIGEST_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL,
    owner TEXT,
    task TEXT NOT NULL,
    due_date TEXT,
    status TEXT DEFAULT 'open',
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner);
CREATE INDEX IF NOT EXISTS idx_tasks_meeting ON tasks(meeting_id);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    context TEXT,
    participants TEXT,
    decided_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_meeting ON decisions(meeting_id);

CREATE TABLE IF NOT EXISTS people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    last_meeting_id TEXT,
    last_meeting_date TEXT,
    meeting_count INTEGER DEFAULT 0,
    topics_discussed TEXT,
    open_task_summary TEXT
);
CREATE INDEX IF NOT EXISTS idx_people_name ON people(name);

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    confidence REAL DEFAULT 1.0
);
CREATE INDEX IF NOT EXISTS idx_topics_meeting ON topics(meeting_id);
CREATE INDEX IF NOT EXISTS idx_topics_topic ON topics(topic);

CREATE TABLE IF NOT EXISTS tasks_archive (
    id INTEGER PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    owner TEXT,
    task TEXT NOT NULL,
    due_date TEXT,
    status TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    archived_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS digest_log (
    meeting_id TEXT PRIMARY KEY,
    digested_at TEXT NOT NULL,
    digest_version INTEGER DEFAULT 1
);
"""


def _db_path(cfg: dict) -> str:
    local_dir = get_local_dir(cfg)
    os.makedirs(local_dir, exist_ok=True)
    return os.path.join(local_dir, "digest.db")


def get_connection(cfg: dict) -> sqlite3.Connection:
    path = _db_path(cfg)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(cfg: dict) -> None:
    conn = get_connection(cfg)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def reset_db(cfg: dict) -> None:
    path = _db_path(cfg)
    if os.path.exists(path):
        os.remove(path)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)
    init_db(cfg)
