"""VTT file ingest pipeline."""
import os
from datetime import datetime

from audio_transcriber.claude_api import summarize_meeting
from audio_transcriber.ingest.vtt_parser import (
    extract_date_from_filename,
    extract_participants,
    extract_start_time,
    parse_vtt,
    utterances_to_plain_text,
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

    plain_text = utterances_to_plain_text(utterances)
    print("Generating summary with Claude...")
    try:
        result = summarize_meeting(plain_text, cfg, has_speakers=True)
        title = result.get("title", "Untitled Meeting")
        summary = result.get("summary", "")
        action_items = result.get("action_items", [])
    except Exception as e:
        print(f"Claude summarization failed: {e}")
        title = "Untitled Meeting"
        summary = ""
        action_items = []

    meeting_data = {
        "source": "vtt_upload",
        "source_file": os.path.basename(vtt_path),
        "date": date,
        "start_time": start_time,
        "end_time": utterances[-1].get("end") if utterances else None,
        "duration_seconds": 0,
        "title": title,
        "app_name": "Microsoft Teams",
        "participants": participants,
        "summary": summary,
        "action_items": action_items,
        "utterances": utterances,
        "has_speakers": True,
        "vtt_path": vtt_path,
    }

    return save_meeting(meeting_data, cfg)
