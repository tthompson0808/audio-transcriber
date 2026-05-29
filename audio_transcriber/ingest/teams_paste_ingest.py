"""Teams paste-text ingest pipeline."""
import os
from datetime import datetime

from audio_transcriber.claude_api import summarize_meeting
from audio_transcriber.ingest.teams_paste_parser import extract_participants, parse_teams_paste
from audio_transcriber.ingest.vtt_parser import extract_date_from_filename, utterances_to_plain_text
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
        "source": "teams_paste",
        "source_file": os.path.basename(file_path),
        "date": date,
        "start_time": start_time,
        "end_time": utterances[-1].get("start") if utterances else None,
        "duration_seconds": 0,
        "title": title,
        "app_name": "Microsoft Teams",
        "participants": participants,
        "summary": summary,
        "action_items": action_items,
        "utterances": utterances,
        "has_speakers": True,
    }

    return save_meeting(meeting_data, cfg)
