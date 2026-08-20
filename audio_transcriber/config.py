"""Windows-adapted config. Paths default to per-user AppData + OneDrive."""
import json
import os
import sys
from pathlib import Path


def _default_data_dir() -> str:
    """OneDrive-synced data folder. Falls back to user home if OneDrive missing."""
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveCommercial")
    if onedrive and os.path.isdir(onedrive):
        return os.path.join(onedrive, "Audio_Transcriber")
    return os.path.join(str(Path.home()), "Audio_Transcriber")


def _default_config_dir() -> str:
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA", str(Path.home())), "Audio_Transcriber")
    return os.path.join(str(Path.home()), ".audio_transcriber")


def _default_local_dir() -> str:
    """For the SQLite digest.db — local-only, fast disk."""
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("LOCALAPPDATA", str(Path.home())), "Audio_Transcriber")
    return os.path.join(str(Path.home()), ".local", "share", "audio_transcriber")


CONFIG_DIR = _default_config_dir()
DEFAULT_CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    # Secrets do NOT live here. They're in Windows Credential Manager via audio_transcriber.auth.credentials.
    "data_dir": _default_data_dir(),
    "local_dir": _default_local_dir(),
    "dashboard": {
        "host": "127.0.0.1",
        "port": 8765,
    },
    "auto_record": {
        "enabled": True,
        "processes": ["Zoom.exe"],  # optional Zoom auto-record. Teams is captured by the always-on teams-auto loop (teams_detect below), NOT here.
        "cancel_window_seconds": 20,
        "poll_interval_seconds": 30,
    },
    # --- Option B: local Teams capture (mic + speakers) + on-device transcription ---
    "capture": {
        "stereo": True,            # record mic (left) + system loopback (right) into one WAV
        "mic_device_index": None,  # None = auto-pick the default WASAPI input
        "loopback_device_index": None,  # None = auto-pick the default output's loopback
        "owner_name": "Me",        # left-channel speaker label (set to the laptop owner, e.g. "Tyson")
        "remote_name": "Remote",   # right-channel speaker label (the other participants)
        "target_sample_rate": 16000,  # final WAV rate fed to the recognizer
        # Primary echo fix: signal-level cancellation. Subtract the loopback
        # (clean speaker output) from the mic before transcription, so the mic
        # channel becomes the owner only. Runs before echo_dedup (the safety net).
        "aec": {
            "enabled": True,
            "filter_taps": 2048,      # ~128 ms echo path at 16 kHz
            "step_size": 0.4,         # NLMS adaptation rate (0..1); lower = stabler, slower
            "max_delay_ms": 500,      # how far to search for the mic-vs-loopback delay
            "geigel_threshold": 2.0,  # freeze adapting when mic peak > this x recent ref peak (owner talking)
        },
        # Secondary net: if any echo still transcribes, the loopback is the clean
        # copy of the remote audio, so drop mic utterances that echo it.
        "echo_dedup": {
            "enabled": True,
            "similarity": 0.6,       # 0..1 full-string fuzzy match to call it an echo
            "token_overlap": 0.7,    # OR: share of the shorter line's words found in the other
            "time_tolerance_s": 2.0, # allow for the acoustic + buffer delay
        },
    },
    "transcribe": {
        "engine": "local",         # "local" (faster-whisper, no API key) | "cloud" (OpenAI Whisper)
        "model": "small.en",       # bump to "medium.en" for production accuracy (slower on CPU)
        "model_dir": None,         # set to a staged snapshot folder for offline/firewalled machines
        "device": "cpu",
        "compute_type": "int8",
        # Leave 2 logical cores free so transcription doesn't compete with
        # whatever the owner is actively doing when a meeting ends.
        "cpu_threads": max(1, (os.cpu_count() or 4) - 2),
        "language": "en",
        "vad_filter": True,        # drop silence → fewer hallucinations + tighter timestamps
    },
    "teams_detect": {
        "method": "mic",           # "mic" = Teams using the microphone (best) | "render" = using speakers
        "process_match": ["ms-teams.exe", "teams.exe"],  # matched case-insensitively
        "path_substr": "Teams",    # extra guard so we match the Teams process tree, not look-alikes
        "poll_interval_seconds": 5,
        "min_active_seconds": 3,   # endpoint must stay ACTIVE/INACTIVE this long before we flip state
    },
    "graph": {
        "poll_interval_seconds": 300,
        "scopes": [
            "OnlineMeetings.Read",
            "OnlineMeetingTranscript.Read.All",
            "Calendars.Read",
            "User.Read",
        ],
    },
    "exclusion": {
        "title_patterns": [
            r"(?i)\bboard\b",
            r"(?i)\bhr\b",
            r"(?i)\blegal\b",
            r"(?i)\bprivileged\b",
            r"(?i)\b1[: ]1\b",
        ],
        "attendee_email_blocklist": [],
    },
    "dedup": {
        "time_window_minutes": 10,
        "duration_tolerance_pct": 20,
    },
    "claude_text_preprocessing": True,
}


def load_config(path: str = None) -> dict:
    path = path or DEFAULT_CONFIG_PATH
    if os.path.exists(path):
        with open(path) as f:
            cfg = json.load(f)
        return _deep_merge(DEFAULT_CONFIG, cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_config(DEFAULT_CONFIG, path)
    return _deep_clone(DEFAULT_CONFIG)


def save_config(cfg: dict, path: str = None) -> None:
    path = path or DEFAULT_CONFIG_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)


def get_data_dir(cfg: dict) -> str:
    return cfg.get("data_dir", DEFAULT_CONFIG["data_dir"])


def get_local_dir(cfg: dict) -> str:
    return cfg.get("local_dir", DEFAULT_CONFIG["local_dir"])


def _deep_merge(base: dict, override: dict) -> dict:
    out = _deep_clone(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _deep_clone(d: dict) -> dict:
    return json.loads(json.dumps(d))
