"""Orchestrator for the `meeting start/stop/status` commands.

The CLI is what Claude Code invokes when the CEO says "start transcribing
my meeting" — no terminal interaction visible to the CEO.

Recording state is persisted as a small JSON in local_dir so `meeting status`
and the tray icon both see the same source of truth.
"""
import json
import os
from datetime import datetime

from audio_transcriber.capture.wasapi_recorder import WasapiRecorder, new_recording_path
from audio_transcriber.config import get_local_dir
from audio_transcriber.transcribe.router import transcribe_and_save


STATE_FILE = "meeting_state.json"
_ACTIVE_RECORDER: WasapiRecorder | None = None  # process-local; survives only within one CLI run


def _state_path(cfg: dict) -> str:
    return os.path.join(get_local_dir(cfg), STATE_FILE)


def _save_state(cfg: dict, state: dict) -> None:
    path = _state_path(cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(state, f)


def _load_state(cfg: dict) -> dict | None:
    path = _state_path(cfg)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _clear_state(cfg: dict) -> None:
    path = _state_path(cfg)
    if os.path.exists(path):
        os.remove(path)


def start(cfg: dict, app_hint: str | None = None) -> dict:
    """Start a manual recording. Returns a status dict."""
    if _load_state(cfg):
        return {"ok": False, "error": "A recording is already active. Stop it first."}

    out_path = new_recording_path(get_local_dir(cfg))
    recorder = WasapiRecorder(out_path)
    recorder.start()

    state = {
        "audio_path": out_path,
        "started_at": datetime.now().isoformat(),
        "app_hint": app_hint or "manual",
        "source": "whisper_recording",
    }
    _save_state(cfg, state)

    global _ACTIVE_RECORDER
    _ACTIVE_RECORDER = recorder
    return {"ok": True, "audio_path": out_path, "started_at": state["started_at"]}


def stop(cfg: dict) -> dict:
    """Stop the active recording, run transcription + synthesis, save the meeting."""
    state = _load_state(cfg)
    if not state:
        return {"ok": False, "error": "No active recording."}

    global _ACTIVE_RECORDER
    audio_path = state["audio_path"]
    duration = 0

    # In the same-process case (interactive CLI), use the live recorder.
    # In the cross-process case (tray icon stopped a scheduled-task recorder),
    # we can't reach the original Python object — caller is responsible for
    # ensuring the WAV file is flushed before invoking stop().
    if _ACTIVE_RECORDER is not None:
        _ACTIVE_RECORDER.stop()
        duration = _ACTIVE_RECORDER.duration_seconds
        _ACTIVE_RECORDER = None

    if not os.path.exists(audio_path):
        _clear_state(cfg)
        return {"ok": False, "error": f"Recording file not found: {audio_path}"}

    try:
        json_path = transcribe_and_save(
            audio_path=audio_path,
            cfg=cfg,
            source=state.get("source", "whisper_recording"),
            app_name=state.get("app_hint"),
            duration_seconds=duration,
        )
    finally:
        _clear_state(cfg)

    return {"ok": True, "saved_to": json_path, "duration_seconds": duration}


def status(cfg: dict) -> dict:
    state = _load_state(cfg)
    if state:
        return {"active": True, **state}
    return {"active": False}
