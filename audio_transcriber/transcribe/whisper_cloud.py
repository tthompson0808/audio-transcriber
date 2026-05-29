"""OpenAI Whisper API client. Single function: WAV -> plain text."""
import os

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from audio_transcriber.auth import credentials


def _get_client():
    if OpenAI is None:
        raise RuntimeError("openai package not installed. pip install openai")
    key = credentials.get_secret("openai_api_key") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("No OpenAI API key. Set via dashboard Settings.")
    return OpenAI(api_key=key)


def transcribe_file(audio_path: str, language: str = "en") -> str:
    """Send an audio file to OpenAI Whisper. Returns plain text."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)
    client = _get_client()
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=language,
            response_format="text",
        )
    # SDK returns a string for response_format="text"
    return result if isinstance(result, str) else getattr(result, "text", "")
