"""Duplicate-meeting detection. Same call can arrive via WASAPI then a later VTT drop."""
import os
import json
from datetime import datetime, timedelta

from audio_transcriber.config import get_data_dir
from audio_transcriber.storage.index import load_index


def _parse_dt(date: str, time: str | None) -> datetime | None:
    if not date:
        return None
    try:
        if time and len(time) >= 5:
            h, m, *rest = time.split(":")
            s = rest[0] if rest else "00"
            return datetime.strptime(f"{date} {int(h):02d}:{int(m):02d}:{int(s):02d}", "%Y-%m-%d %H:%M:%S")
        return datetime.strptime(date, "%Y-%m-%d")
    except (ValueError, IndexError):
        return None


def find_duplicate(new: dict, cfg: dict) -> str | None:
    """Return the meeting_id of an existing row that matches `new`, or None.

    Match rule: same day, start within ±time_window_minutes, duration within
    ±duration_tolerance_pct (when both have duration_seconds > 0).
    """
    dedup_cfg = cfg.get("dedup", {})
    window_min = dedup_cfg.get("time_window_minutes", 10)
    dur_tol = dedup_cfg.get("duration_tolerance_pct", 20) / 100.0

    new_dt = _parse_dt(new.get("date"), new.get("start_time"))
    if not new_dt:
        return None
    new_dur = new.get("duration_seconds", 0)

    index = load_index(cfg)
    data_dir = get_data_dir(cfg)
    for entry in index["meetings"]:
        if entry["date"] != new.get("date"):
            continue
        existing_path = os.path.join(data_dir, "meetings", entry["path"])
        try:
            with open(existing_path) as f:
                existing = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        ex_dt = _parse_dt(existing.get("date"), existing.get("start_time"))
        if not ex_dt:
            continue
        if abs((new_dt - ex_dt).total_seconds()) > window_min * 60:
            continue

        ex_dur = existing.get("duration_seconds", 0)
        if new_dur > 0 and ex_dur > 0:
            avg = (new_dur + ex_dur) / 2
            if abs(new_dur - ex_dur) / avg > dur_tol:
                continue

        return entry["id"]

    return None
