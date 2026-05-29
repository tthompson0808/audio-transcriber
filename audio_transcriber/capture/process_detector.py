"""Windows process watcher — detects target meeting apps via psutil.

Runs as a tight poll loop driven by a Windows scheduled task (every 30s).
On rising edge of detection, calls on_meeting_started callback.
On falling edge, calls on_meeting_ended.
"""
import time

try:
    import psutil
except ImportError:
    psutil = None  # Dev on Mac without psutil installed — module still imports.

_LAST_SEEN: set[str] = set()


def list_running_meeting_processes(target_names: list[str]) -> set[str]:
    """Return the subset of target_names currently running."""
    if psutil is None:
        return set()
    seen = set()
    targets_lower = {n.lower() for n in target_names}
    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if name in targets_lower:
                seen.add(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return seen


def tick(cfg: dict, on_started, on_ended) -> None:
    """One detector tick. Compares against last seen and fires callbacks.

    Callbacks receive a single arg: the process name (e.g. "zoom.exe").
    """
    global _LAST_SEEN
    targets = cfg.get("auto_record", {}).get("processes", [])
    if not targets:
        return

    current = list_running_meeting_processes(targets)
    started = current - _LAST_SEEN
    ended = _LAST_SEEN - current

    for name in started:
        try:
            on_started(name)
        except Exception as e:
            print(f"on_started callback failed for {name}: {e}")

    for name in ended:
        try:
            on_ended(name)
        except Exception as e:
            print(f"on_ended callback failed for {name}: {e}")

    _LAST_SEEN = current


def run_forever(cfg: dict, on_started, on_ended) -> None:
    """Block and tick at the configured interval. For dev/manual runs only —
    production uses Windows scheduled tasks to invoke tick() periodically."""
    interval = cfg.get("auto_record", {}).get("poll_interval_seconds", 30)
    while True:
        tick(cfg, on_started, on_ended)
        time.sleep(interval)
