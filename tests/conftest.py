"""Shared fixtures."""
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_cfg(tmp_path):
    """A minimal config pointing at tmp dirs. No real API keys needed."""
    data_dir = tmp_path / "data"
    local_dir = tmp_path / "local"
    data_dir.mkdir()
    local_dir.mkdir()
    return {
        "data_dir": str(data_dir),
        "local_dir": str(local_dir),
        "dashboard": {"host": "127.0.0.1", "port": 8765},
        "auto_record": {"enabled": True, "processes": ["Zoom.exe"], "cancel_window_seconds": 20, "poll_interval_seconds": 30},
        "graph": {"poll_interval_seconds": 300, "scopes": []},
        "exclusion": {"title_patterns": [r"(?i)\bboard\b", r"(?i)\bhr\b"], "attendee_email_blocklist": ["@legalcounsel.com"]},
        "dedup": {"time_window_minutes": 10, "duration_tolerance_pct": 20},
    }
