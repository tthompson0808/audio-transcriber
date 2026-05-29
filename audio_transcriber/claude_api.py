"""Anthropic client. Key resolution: cfg -> Credential Manager -> env var."""
import os
from anthropic import Anthropic

from audio_transcriber.auth import credentials


def get_client(cfg: dict) -> Anthropic:
    api_key = (
        cfg.get("anthropic_api_key")
        or credentials.get_secret("anthropic_api_key")
        or os.environ.get("ANTHROPIC_API_KEY")
    )
    if not api_key:
        raise ValueError(
            "No Anthropic API key. Set via dashboard Settings, or run: "
            "audio_transcriber set-key anthropic <key>"
        )
    return Anthropic(api_key=api_key)


def summarize_meeting(raw_transcript: str, cfg: dict, has_speakers: bool = True) -> dict:
    """Synthesize a meeting transcript.

    has_speakers branches the prompt:
      - True: emphasize per-person ownership of action items
      - False: ask Claude to infer ownership; mark unclear ones as "(unattributed)"
    """
    client = get_client(cfg)

    if has_speakers:
        system = """You process meeting transcripts that include named speakers. Return a JSON object with exactly these keys:
- "title": short descriptive meeting title (3-8 words)
- "summary": exactly 3 sentences summarizing the meeting
- "action_items": array of objects, each with {"owner": "Person name", "task": "What they need to do", "due": "YYYY-MM-DD or null"}. Owner MUST be a real participant name from the transcript. If a commitment is made ("I'll send it Friday"), the owner is the speaker who said it. If no clear owner, omit the item. Set due to null when no deadline was stated.
- "participants": array of participant name strings from the transcript.
- "utterances": array of objects, each with {"speaker": "Person name or Unknown", "start": "HH:MM:SS or null", "end": null, "text": "What they said."}. Clean up filler words (um, uh, like, you know), fix obvious grammar. Preserve timestamps from the original if present.

Return ONLY valid JSON. No markdown fencing."""
    else:
        system = """You process meeting transcripts that DO NOT have named speakers (raw transcription from an audio recording). Return a JSON object with exactly these keys:
- "title": short descriptive meeting title (3-8 words)
- "summary": exactly 3 sentences summarizing the meeting
- "action_items": array of objects, each with {"owner": "(unattributed)" | "Speaker A" | "Speaker B" | ... | "the team", "task": "What needs to be done", "due": "YYYY-MM-DD or null", "confidence": "high" | "low"}. Since speakers are unknown, default owner to "(unattributed)" unless context strongly suggests one party. Use "Speaker A/B/C" only when distinct voices are clearly addressed. Set confidence to "low" by default; only "high" if the commitment is unambiguous.
- "participants": always return [] — speakers are unknown.
- "utterances": array of objects, each with {"speaker": "Unknown", "start": null, "end": null, "text": "What was said."}. Break long monologues into ~30-second chunks at natural sentence breaks. Clean up filler words.

Return ONLY valid JSON. No markdown fencing."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": raw_transcript}],
    )
    import json
    return json.loads(response.content[0].text)
