"""Schema parity: new digest.db must match Tyler's AudioTools digest.db
column-for-column. This is the contract downstream agents rely on.
"""
import os
import sqlite3
from pathlib import Path

import pytest

from audio_transcriber.digest.db import SCHEMA_SQL as NEW_DDL

TYLERS_DDL_PATH = Path("/Users/tyler/AudioTools/src/digest/db.py")


def _extract_ddl_from_file(py_path: Path) -> str:
    src = py_path.read_text()
    start = src.index("SCHEMA_SQL =")
    quote_open = src.index('"""', start) + 3
    quote_close = src.index('"""', quote_open)
    return src[quote_open:quote_close]


def _schema_dict(ddl: str) -> dict[str, list[tuple]]:
    """Return {table_name: [(col_name, col_type, notnull, dflt, pk), ...]}."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(ddl)
    out = {}
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall():
        cols = []
        for row in conn.execute(f"PRAGMA table_info('{name}')"):
            # (cid, name, type, notnull, dflt_value, pk)
            cols.append(row[1:])
        out[name] = sorted(cols)
    conn.close()
    return out


def test_schema_parity():
    if not TYLERS_DDL_PATH.exists():
        pytest.skip(f"Tyler's AudioTools not at {TYLERS_DDL_PATH} — skipping parity check")
    old = _schema_dict(_extract_ddl_from_file(TYLERS_DDL_PATH))
    new = _schema_dict(NEW_DDL)
    assert set(old.keys()) == set(new.keys()), (
        f"Tables differ.\n  only-in-tyler: {set(old) - set(new)}\n  only-in-new:   {set(new) - set(old)}"
    )
    for table in old:
        assert old[table] == new[table], f"Columns for table '{table}' differ.\n  old: {old[table]}\n  new: {new[table]}"


def test_digest_db_initializes(tmp_cfg):
    from audio_transcriber.digest.db import init_db, get_connection
    init_db(tmp_cfg)
    conn = get_connection(tmp_cfg)
    tables = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    expected = {"tasks", "decisions", "people", "topics", "tasks_archive", "digest_log"}
    assert expected.issubset(tables)
