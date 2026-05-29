"""Transcription router — turns any audio inflow into a SAVED-BUT-PENDING meeting.

Whisper still runs here (speech-to-text). Claude synthesis (title, summary,
action items, decisions) is deferred to Claude Desktop or the API fallback —
see synthesize/pending.py.

Used by:
  - WASAPI recorder (inflow 2: auto-record Zoom)
  - Dropzone watcher when an audio/video file is dropped (inflow 3)
  - CLI 'meeting stop' (manual Claude Code trigger)
"""
import os
from datetime import datetime

from audio_transcriber.storage.manager import save_meeting
from audio_transcriber.transcribe.whisper_cloud import transcribe_file


def transcribe_and_save(
    audio_path: str,
    cfg: dict,
    source: str,
    app_name: str | None = None,
    title_hint: str | None = None,
    duration_seconds: int = 0,
) -> str:
    """Run an audio file: Whisper -> saved meeting (synthesis pending).

    `source` is one of: "whisper_recording" (WASAPI), "whisper_dropzone" (file drop).
    """
    print(f"Transcribing {os.path.basename(audio_path)} via Whisper API...")
    text = transcribe_file(audio_path)

    if not text.strip():
        print("Whisper returned empty transcript — saving an empty-meeting stub.")

    now = datetime.now()
    meeting_data = {
        "source": source,
        "source_file": os.path.basename(audio_path),
        "date": now.strftime("%Y-%m-%d"),
        "start_time": now.strftime("%H:%M:%S"),
        "end_time": None,
        "duration_seconds": duration_seconds,
        "title": title_hint or f"Untitled — {os.path.basename(audio_path)}",
        "app_name": app_name,
        "participants": [],
        "summary": "",  # synthesis pending — Claude Desktop or API fallback fills this in
        "action_items": [],
        "utterances": [
            {"speaker": "Unknown", "start": None, "end": None, "text": text}
        ],
        "has_speakers": False,
        "audio_path": audio_path,
    }

    return save_meeting(meeting_data, cfg)
