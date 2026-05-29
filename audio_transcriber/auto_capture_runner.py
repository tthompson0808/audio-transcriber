"""Auto-capture runner — driven by Windows scheduled task every 30s.

On each tick:
  - Run process detector to find rising/falling edges of Zoom.exe
  - On rising edge: check exclusion list against window title, then either
    start a recording (managed by tray-aware state file) or log a skip
  - On falling edge: stop the recording, route through Whisper + Claude

The recording is owned by THIS process, so the same scheduled-task invocation
should start AND stop the recording. For cross-tick continuity (a meeting
that runs longer than 30s), we either:
  - keep a long-running runner (`audio_transcriber.runner serve` mode), OR
  - rely on the scheduled task firing again; we detect "process still running
    AND state file already says recording" and no-op.

Simpler model implemented here: run as a long-lived background process
launched at login (Windows Task Scheduler "at logon" trigger). The
scheduled "every 30s" pattern is replaced by an internal loop.
"""
import argparse
import sys
import time

from audio_transcriber.capture import meeting as meeting_mod, process_detector, window_title
from audio_transcriber.capture.exclusion import should_record
from audio_transcriber.config import load_config


def _on_started(name: str, cfg: dict):
    if not cfg.get("auto_record", {}).get("enabled", True):
        print(f"Auto-record disabled — skipping {name}")
        return
    title = window_title.get_meeting_title(name) or name
    allowed, msg = should_record(title, [], cfg)
    if not allowed:
        print(f"{name} ({title}): {msg}")
        return
    state = meeting_mod.status(cfg)
    if state.get("active"):
        print(f"Recording already active — ignoring new {name}")
        return
    print(f"{name} detected ({title}) — starting recording")
    meeting_mod.start(cfg, app_hint=name)


def _on_ended(name: str, cfg: dict):
    state = meeting_mod.status(cfg)
    if not state.get("active"):
        return
    if state.get("app_hint") != name:
        return
    print(f"{name} ended — stopping recording and processing")
    result = meeting_mod.stop(cfg)
    print(result)


def serve():
    cfg = load_config()
    interval = cfg.get("auto_record", {}).get("poll_interval_seconds", 30)
    print(f"Auto-capture runner started (poll every {interval}s)")
    while True:
        try:
            process_detector.tick(
                cfg,
                on_started=lambda n: _on_started(n, cfg),
                on_ended=lambda n: _on_ended(n, cfg),
            )
        except Exception as e:
            print(f"Tick error: {e}")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(prog="audio_transcriber.auto_capture_runner")
    parser.add_argument("mode", choices=["serve", "tick"], default="serve", nargs="?")
    args = parser.parse_args()
    if args.mode == "serve":
        serve()
    else:
        cfg = load_config()
        process_detector.tick(
            cfg,
            on_started=lambda n: _on_started(n, cfg),
            on_ended=lambda n: _on_ended(n, cfg),
        )


if __name__ == "__main__":
    main()
