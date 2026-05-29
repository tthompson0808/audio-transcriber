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
        "processes": ["Zoom.exe"],  # Teams handled via Graph poller, not WASAPI
        "cancel_window_seconds": 20,
        "poll_interval_seconds": 30,
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
