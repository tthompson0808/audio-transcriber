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

# teams-auto is a long-lived process — the model only needs loading once per
# (ref, device, compute_type, cpu_threads) combo, not on every meeting.
_MODEL_CACHE: dict = {}


def load_model(cfg: dict):
    if WhisperModel is None:
        raise RuntimeError("faster-whisper not installed. pip install faster-whisper")
    t = cfg.get("transcribe", {})
    # A staged snapshot folder (offline) wins; otherwise load by name (may download).
    model_ref = t.get("model_dir") or t.get("model", "small.en")
    device = t.get("device", "cpu")
    compute_type = t.get("compute_type", "int8")
    # cpu_threads=0 (the faster-whisper default) lets CTranslate2 grab every
    # logical core, which pegs the whole machine for the length of the
    # transcription. Cap it so the foreground app stays responsive.
    cpu_threads = t.get("cpu_threads", 4)
    key = (model_ref, device, compute_type, cpu_threads)
    cached = _MODEL_CACHE.get(key)
    if cached is not None:
        return cached
    model = WhisperModel(
        model_ref,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,
    )
    _MODEL_CACHE[key] = model
    return model


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
    lang = t.get("language", "en")
    want_vad = t.get("vad_filter", True)
    try:
        segments, _info = model.transcribe(audio, language=lang, vad_filter=want_vad)
        segs = list(segments)  # force inference now so a VAD error surfaces here
    except Exception as e:
        if not want_vad:
            raise
        print(f"VAD unavailable ({e}); transcribing without it.")
        segments, _info = model.transcribe(audio, language=lang, vad_filter=False)
        segs = list(segments)
    out = []
    for seg in segs:
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


def _text_echo(a: str, b: str, ratio_thr: float, token_thr: float) -> bool:
    """True if `a` looks like an echo of `b`.

    Two complementary tests: a full-string fuzzy ratio (catches near-identical
    lines) OR token containment (catches the case where the mic only caught a
    fragment/prefix of what the speakers played, e.g. "it's crazy you built this"
    vs "it's crazy you built this, it's like teams, but you just made it").
    """
    a, b = a.lower(), b.lower()
    if difflib.SequenceMatcher(None, a, b).ratio() >= ratio_thr:
        return True
    at, bt = set(a.split()), set(b.split())
    if at and bt and len(at & bt) / min(len(at), len(bt)) >= token_thr:
        return True
    return False


def _dedup_echo(owner_utts: list[dict], remote_utts: list[dict], cap: dict) -> tuple[list[dict], int]:
    """Drop owner (mic) utterances that echo a remote (loopback) utterance.

    An owner utterance is an echo if it overlaps a remote utterance in time
    (within tolerance) and their text matches. The loopback is the clean source,
    so the remote copy is the one we keep.
    """
    ed = cap.get("echo_dedup", {})
    ratio_thr = ed.get("similarity", 0.6)
    token_thr = ed.get("token_overlap", 0.7)
    tol = ed.get("time_tolerance_s", 2.0)
    kept, dropped = [], 0
    for o in owner_utts:
        is_echo = any(
            o["_start_s"] <= r["_end_s"] + tol
            and o["_end_s"] >= r["_start_s"] - tol
            and _text_echo(o["text"], r["text"], ratio_thr, token_thr)
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
        if cap.get("aec", {}).get("enabled", True):
            from audio_transcriber.transcribe.echo_cancel import cancel_echo
            channels[0] = cancel_echo(channels[0], channels[1], _TARGET_RATE, cfg)
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
