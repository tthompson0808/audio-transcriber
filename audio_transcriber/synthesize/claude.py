"""Synthesis facade. Re-exports the speaker-aware summarizer."""
from audio_transcriber.claude_api import summarize_meeting


def summarize_transcript(raw_transcript: str, cfg: dict, has_speakers: bool = True) -> dict:
    """Summarize a transcript. `has_speakers=False` for Whisper-recorded audio."""
    if not raw_transcript.strip():
        return {
            "title": "Empty Meeting",
            "summary": "No audio was captured or transcribed.",
            "action_items": [],
            "participants": [],
            "utterances": [],
        }

    try:
        result = summarize_meeting(raw_transcript, cfg, has_speakers=has_speakers)
        return {
            "title": result.get("title", "Untitled Meeting"),
            "summary": result.get("summary", ""),
            "action_items": result.get("action_items", []),
            "participants": result.get("participants", []),
            "utterances": result.get("utterances", []),
        }
    except Exception as e:
        print(f"Claude summarization failed: {e}")
        return {
            "title": "Untitled Meeting",
            "summary": "",
            "action_items": [],
            "participants": [],
            "utterances": [{"speaker": "Unknown", "start": None, "end": None, "text": raw_transcript}],
        }
