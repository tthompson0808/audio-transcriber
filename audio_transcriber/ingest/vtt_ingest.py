"""VTT file ingest pipeline. Queues for later synthesis (does not call Claude here)."""
import os
from datetime import datetime

from audio_transcriber.ingest.vtt_parser import (
    extract_date_from_filename,
    extract_participants,
    extract_start_time,
    parse_vtt,
)
from audio_transcriber.storage.manager import save_meeting


def ingest_vtt(vtt_path: str, cfg: dict) -> str:
    vtt_path = os.path.expanduser(vtt_path)
    if not os.path.exists(vtt_path):
        raise FileNotFoundError(f"VTT file not found: {vtt_path}")

    with open(vtt_path, encoding="utf-8") as f:
        vtt_text = f.read()

    utterances = parse_vtt(vtt_text)
    participants = extract_participants(utterances)
    date = extract_date_from_filename(os.path.basename(vtt_path)) or datetime.now().strftime("%Y-%m-%d")
    start_time = extract_start_time(utterances)

    meeting_data = {
        "source": "vtt_upload",
        "source_file": os.path.basename(vtt_path),
        "date": date,
        "start_time": start_time,
        "end_time": utterances[-1].get("end") if utterances else None,
        "duration_seconds": 0,
        "title": f"Untitled — {os.path.basename(vtt_path)}",
        "app_name": "Microsoft Teams",
        "participants": participants,
        "summary": "",  # filled in by Claude Desktop synthesis or API fallback
        "action_items": [],
        "utterances": utterances,
        "has_speakers": True,
        "vtt_path": vtt_path,
    }

    return save_meeting(meeting_data, cfg)
