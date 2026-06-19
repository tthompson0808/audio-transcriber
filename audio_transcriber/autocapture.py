"""Always-on launcher for Teams auto-capture, with a crash log.

The scheduled task / Startup shortcut runs THIS (via pythonw, windowless) instead
of calling `teams-auto serve` directly. Two reasons:

  1. A windowless launch has no console, so a crash (even an import-time one, the
     most common "it died at install" case) would otherwise be completely silent.
     Here everything is redirected to a log file first, so the next run always
     leaves a trace at:  %LOCALAPPDATA%\\Audio_Transcriber\\logs\\auto_capture.log
  2. The data + recordings folders are created before the loop starts, so a fresh
     machine always has its working directories (no "did not create a directory").

Pause/resume and all other CLI commands are unchanged; this only wraps the serve loop.
"""
import datetime
import os
import sys
import traceback


def _log_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    logdir = os.path.join(base, "Audio_Transcriber", "logs")
    os.makedirs(logdir, exist_ok=True)
    return os.path.join(logdir, "auto_capture.log")


def _run() -> None:
    # Redirect stdout+stderr to the log before anything else, so an import error
    # below is captured rather than vanishing into a windowless process.
    log = open(_log_path(), "a", encoding="utf-8", buffering=1)
    sys.stdout = log
    sys.stderr = log
    print(f"\n=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} auto-capture starting "
          f"(pid {os.getpid()}, exe {sys.executable}) ===")
    try:
        from audio_transcriber.config import load_config, get_local_dir
        from audio_transcriber.capture.teams_auto import serve

        cfg = load_config()
        # Create the working folders up front so the first save never fails and
        # onboarding can point at a real path.
        for sub in (os.path.join(cfg.get("data_dir", ""), "meetings"),
                    os.path.join(get_local_dir(cfg), "recordings")):
            if sub:
                os.makedirs(sub, exist_ok=True)
        # Log the resolved paths every start: if the config did not load (wrong
        # profile, etc.) the model_dir/data_dir here will show it immediately.
        print(f"data_dir={cfg.get('data_dir')!r}  "
              f"local_dir={get_local_dir(cfg)!r}  "
              f"model_dir={cfg.get('transcribe', {}).get('model_dir')!r}")
        serve(cfg)
    except Exception:
        print("CRASHED:")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    _run()
