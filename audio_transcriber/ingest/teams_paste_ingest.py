"""Teams paste-text ingest pipeline. Queues for later synthesis (no Claude call here)."""
import os
from datetime import datetime

from audio_transcriber.ingest.teams_paste_parser import extract_participants, parse_teams_paste
from audio_transcriber.ingest.vtt_parser import extract_date_from_filename
from audio_transcriber.storage.manager import save_meeting


def ingest_teams_paste(file_path: str, cfg: dict) -> str:
    file_path = os.path.expanduser(file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        text = f.read()

    utterances = parse_teams_paste(text)
    if not utterances:
        raise ValueError("No utterances parsed from file. Check the format.")

    participants = extract_participants(utterances)
    date = extract_date_from_filename(os.path.basename(file_path)) or datetime.now().strftime("%Y-%m-%d")
    start_time = utterances[0].get("start") if utterances else None

    meeting_data = {
        "source": "teams_paste",
        "source_file": os.path.basename(file_path),
        "date": date,
        "start_time": start_time,
        "end_time": utterances[-1].get("start") if utterances else None,
        "duration_seconds": 0,
        "title": f"Untitled — {os.path.basename(file_path)}",
        "app_name": "Microsoft Teams",
        "participants": participants,
        "summary": "",
        "action_items": [],
        "utterances": utterances,
        "has_speakers": True,
    }

    return save_meeting(meeting_data, cfg)
