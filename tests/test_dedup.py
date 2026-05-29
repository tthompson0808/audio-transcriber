"""Dedup detects same-meeting overlap from two inflows."""
import json
import os

from audio_transcriber.capture.dedup import find_duplicate
from audio_transcriber.storage.index import add_to_index


def _seed_meeting(cfg, meeting_id, date, start_time, duration, title="Sync"):
    month = date[:7]
    meeting_path = os.path.join(cfg["data_dir"], "meetings", month, f"{meeting_id}.json")
    os.makedirs(os.path.dirname(meeting_path), exist_ok=True)
    with open(meeting_path, "w") as f:
        json.dump({
            "id": meeting_id,
            "date": date,
            "start_time": start_time,
            "duration_seconds": duration,
            "title": title,
            "source": "graph_teams",
        }, f)
    add_to_index({
        "id": meeting_id,
        "date": date,
        "title": title,
        "source": "graph_teams",
        "participants": [],
        "path": f"{month}/{meeting_id}.json",
    }, cfg)


def test_duplicate_within_window_matches(tmp_cfg):
    _seed_meeting(tmp_cfg, "mtg_existing", "2026-05-29", "10:00:00", 1800)
    new = {"date": "2026-05-29", "start_time": "10:05:00", "duration_seconds": 1700}
    assert find_duplicate(new, tmp_cfg) == "mtg_existing"


def test_outside_time_window_does_not_match(tmp_cfg):
    _seed_meeting(tmp_cfg, "mtg_existing", "2026-05-29", "10:00:00", 1800)
    new = {"date": "2026-05-29", "start_time": "11:30:00", "duration_seconds": 1800}
    assert find_duplicate(new, tmp_cfg) is None


def test_different_duration_does_not_match(tmp_cfg):
    _seed_meeting(tmp_cfg, "mtg_existing", "2026-05-29", "10:00:00", 1800)
    # within time window but duration off by 60%
    new = {"date": "2026-05-29", "start_time": "10:05:00", "duration_seconds": 4500}
    assert find_duplicate(new, tmp_cfg) is None


def test_different_day_does_not_match(tmp_cfg):
    _seed_meeting(tmp_cfg, "mtg_existing", "2026-05-29", "10:00:00", 1800)
    new = {"date": "2026-05-30", "start_time": "10:00:00", "duration_seconds": 1800}
    assert find_duplicate(new, tmp_cfg) is None
