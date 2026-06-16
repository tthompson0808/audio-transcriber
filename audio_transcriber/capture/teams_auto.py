"""Auto-capture loop for Teams meetings — the heart of Option B.

A long-lived process (launched at logon by a scheduled task) that:
  1. polls the Teams meeting detector (mic-in-use)
  2. on a debounced rising edge → starts a stereo recording (mic L + speakers R)
  3. on a debounced falling edge → stops, transcribes on-device, queues pending

No API keys. Synthesis is done later by Claude Desktop via the MCP server.

Debounce is symmetric: the endpoint must stay ACTIVE for `min_active_seconds`
before we start, and stay INACTIVE that long before we stop — so a notification
ding or a momentary silence never flaps the recorder.
"""
import time

from audio_transcriber.capture.teams_session_detector import teams_meeting_active
from audio_transcriber.capture.wasapi_recorder import DualStreamRecorder, new_recording_path
from audio_transcriber.config import get_local_dir
from audio_transcriber.transcribe.router import transcribe_and_save

try:
    import comtypes
except ImportError:
    comtypes = None


def serve(cfg: dict) -> None:
    if comtypes is not None:
        try:
            comtypes.CoInitialize()
        except Exception:
            pass

    td = cfg.get("teams_detect", {})
    interval = td.get("poll_interval_seconds", 2)
    debounce = td.get("min_active_seconds", 3)
    print(f"Teams auto-capture started (poll {interval}s, debounce {debounce}s, "
          f"method '{td.get('method', 'mic')}')")

    recorder = None
    path = None
    active_since = None
    inactive_since = None

    while True:
        try:
            active = teams_meeting_active(cfg)
            now = time.monotonic()

            if active:
                inactive_since = None
                if recorder is None:
                    active_since = active_since or now
                    if now - active_since >= debounce:
                        path = new_recording_path(get_local_dir(cfg))
                        recorder = DualStreamRecorder(path, cfg)
                        recorder.start()
                        print(f"Meeting detected — recording → {path}")
            else:
                active_since = None
                if recorder is not None:
                    inactive_since = inactive_since or now
                    if now - inactive_since >= debounce:
                        _finish(recorder, path, cfg)
                        recorder, path, inactive_since = None, None, None
        except Exception as e:
            print(f"Tick error: {e}")
        time.sleep(interval)


def _finish(recorder, path: str, cfg: dict) -> None:
    duration = recorder.duration_seconds
    recorder.stop()
    lv = recorder.levels
    print(f"Meeting ended ({duration}s, channels={lv['channels']}, "
          f"L_rms={lv['left_rms']:.4f} R_rms={lv['right_rms']:.4f}) — transcribing on-device...")
    try:
        json_path = transcribe_and_save(
            audio_path=path,
            cfg=cfg,
            source="teams_local",
            app_name="Microsoft Teams",
            duration_seconds=duration,
        )
        print(f"Saved (pending synthesis) → {json_path}")
    except Exception as e:
        print(f"Transcription/save failed (audio kept at {path}): {e}")


def main() -> None:
    from audio_transcriber.config import load_config
    serve(load_config())


if __name__ == "__main__":
    main()
