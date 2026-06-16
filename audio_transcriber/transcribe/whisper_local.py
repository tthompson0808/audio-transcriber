"""On-device speech-to-text via faster-whisper. No API key, no network at run time.

Reads a WAV and returns utterances in the canonical schema
({speaker, start, end, text}). For a stereo capture (mic=LEFT, loopback=RIGHT)
it transcribes each channel separately and labels them owner vs. remote — cheap
two-way speaker separation without a diarization model.

faster-whisper is fed a float32 numpy array at 16 kHz, so PyAV/ffmpeg decoding
is never exercised at run time (one less moving part on a locked-down machine).
"""
import difflib
import wave

try:
    import numpy as np
except ImportError:
    np = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

from audio_transcriber.capture.wasapi_recorder import _resample

_TARGET_RATE = 16000


# Friendly model name → faster-whisper (CTranslate2) HF repo, for offline staging.
MODEL_REPOS = {
    "tiny.en": "Systran/faster-whisper-tiny.en",
    "base.en": "Systran/faster-whisper-base.en",
    "small.en": "Systran/faster-whisper-small.en",
    "medium.en": "Systran/faster-whisper-medium.en",
    "large-v3": "Systran/faster-whisper-large-v3",
}


def load_model(cfg: dict):
    if WhisperModel is None:
        raise RuntimeError("faster-whisper not installed. pip install faster-whisper")
    t = cfg.get("transcribe", {})
    # A staged snapshot folder (offline) wins; otherwise load by name (may download).
    model_ref = t.get("model_dir") or t.get("model", "small.en")
    return WhisperModel(
        model_ref,
        device=t.get("device", "cpu"),
        compute_type=t.get("compute_type", "int8"),
    )


def _read_channels(path: str):
    """WAV → (list of mono float32 arrays per channel, sample_rate)."""
    if np is None:
        raise RuntimeError("numpy not installed. pip install numpy")
    with wave.open(path, "rb") as w:
        rate, ch = w.getframerate(), w.getnchannels()
        raw = w.readframes(w.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        samples = samples.reshape(-1, ch)
        return [samples[:, c].copy() for c in range(ch)], rate
    return [samples], rate


def _fmt_ts(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _transcribe_array(model, audio, cfg: dict, speaker: str) -> list[dict]:
    t = cfg.get("transcribe", {})
    segments, _info = model.transcribe(
        audio,
        language=t.get("language", "en"),
        vad_filter=t.get("vad_filter", False),
    )
    out = []
    for seg in segments:  # generator — iterating is what runs inference
        text = (seg.text or "").strip()
        if not text:
            continue
        out.append({
            "speaker": speaker,
            "start": _fmt_ts(seg.start),
            "end": _fmt_ts(seg.end),
            "text": text,
            "_start_s": float(seg.start),
            "_end_s": float(seg.end),
        })
    return out


def _similar(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _dedup_echo(owner_utts: list[dict], remote_utts: list[dict], cap: dict) -> tuple[list[dict], int]:
    """Drop owner (mic) utterances that echo a remote (loopback) utterance.

    An owner utterance is an echo if it overlaps a remote utterance in time
    (within tolerance) and their text is similar enough. The loopback is the
    clean source, so the remote copy is the one we keep.
    """
    ed = cap.get("echo_dedup", {})
    thr = ed.get("similarity", 0.6)
    tol = ed.get("time_tolerance_s", 2.0)
    kept, dropped = [], 0
    for o in owner_utts:
        is_echo = any(
            o["_start_s"] <= r["_end_s"] + tol
            and o["_end_s"] >= r["_start_s"] - tol
            and _similar(o["text"], r["text"]) >= thr
            for r in remote_utts
        )
        if is_echo:
            dropped += 1
        else:
            kept.append(o)
    return kept, dropped


def transcribe_auto(wav_path: str, cfg: dict) -> tuple[list[dict], bool, list[str]]:
    """Transcribe a WAV → (utterances, has_speakers, participants).

    Stereo + capture.stereo → per-channel owner/remote labels (has_speakers=True).
    Otherwise a single 'Unknown' speaker (has_speakers=False).
    """
    cap = cfg.get("capture", {})
    channels, rate = _read_channels(wav_path)
    if rate != _TARGET_RATE:
        channels = [_resample(c, rate, _TARGET_RATE) for c in channels]

    model = load_model(cfg)

    if len(channels) >= 2 and cap.get("stereo", True):
        owner = cap.get("owner_name", "Me")
        remote = cap.get("remote_name", "Remote")
        owner_utts = _transcribe_array(model, channels[0], cfg, owner)
        remote_utts = _transcribe_array(model, channels[1], cfg, remote)

        if cap.get("echo_dedup", {}).get("enabled", True):
            owner_utts, dropped = _dedup_echo(owner_utts, remote_utts, cap)
            if dropped:
                print(f"Echo dedup: dropped {dropped} mic utterance(s) that echoed the speakers.")

        utterances = owner_utts + remote_utts
        utterances.sort(key=lambda u: u["_start_s"])
        for u in utterances:
            u.pop("_start_s", None)
            u.pop("_end_s", None)
        return utterances, True, [owner, remote]

    utterances = _transcribe_array(model, channels[0], cfg, "Unknown")
    for u in utterances:
        u.pop("_start_s", None)
        u.pop("_end_s", None)
    return utterances, False, []
