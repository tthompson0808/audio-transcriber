"""Detect a Teams *meeting* (not just Teams being open) via audio sessions.

Teams' process runs the whole time the app is open, so process detection can't
bound a meeting. The reliable signal is "Teams is actively using an audio
endpoint":

  method="mic"    → Teams holds an ACTIVE session on the capture (microphone)
                    device. Teams grabs the mic for the entire call, even when
                    nobody is talking → the most robust signal.
  method="render" → Teams holds an ACTIVE session on the speakers. Easier to
                    read, but can briefly drop to INACTIVE when the far side is
                    silent, so it needs a longer debounce.

`watch()` prints BOTH every tick so we can confirm on real hardware which signal
is rock-solid for this machine, then lock it via config (teams_detect.method).
Everything is import-guarded so the module still loads on macOS for dev.
"""
import time

try:
    import comtypes
    from pycaw.pycaw import AudioUtilities, IAudioSessionControl2, IAudioSessionManager2
except ImportError:
    comtypes = None
    AudioUtilities = None
    IAudioSessionControl2 = None

try:
    import psutil
except ImportError:
    psutil = None

# AudioSessionState enum (Windows Core Audio)
_INACTIVE, _ACTIVE, _EXPIRED = 0, 1, 2
_STATE_NAME = {-1: "?", 0: "INACTIVE", 1: "ACTIVE", 2: "EXPIRED"}


def _available() -> bool:
    return AudioUtilities is not None and comtypes is not None


def _proc_name(pid: int) -> str:
    if not pid or psutil is None:
        return ""
    try:
        return psutil.Process(pid).name()
    except Exception:
        return ""


def _proc_path(pid: int) -> str:
    if not pid or psutil is None:
        return ""
    try:
        return psutil.Process(pid).exe() or ""
    except Exception:
        return ""


def _is_teams(pid: int, name: str, cfg: dict) -> bool:
    td = cfg.get("teams_detect", {})
    names = [n.lower() for n in td.get("process_match", [])]
    substr = (td.get("path_substr") or "").lower()
    name = (name or _proc_name(pid)).lower()
    path = _proc_path(pid).lower()
    if name in names:
        return True
    if substr and (substr in path or substr in name):
        return True
    return False


def _pid_of(session) -> int:
    try:
        if session.Process is not None:
            return session.Process.pid
    except Exception:
        pass
    try:
        return session._ctl.GetProcessId()
    except Exception:
        return 0


def _state_of(session) -> int:
    try:
        return session._ctl.GetState()
    except Exception:
        try:
            return session.State
        except Exception:
            return -1


def render_sessions() -> list[tuple[int, str, int]]:
    """(pid, process_name, state) for every session on the default speakers."""
    if not _available():
        return []
    out = []
    try:
        for s in AudioUtilities.GetAllSessions():
            pid = _pid_of(s)
            out.append((pid, _proc_name(pid), _state_of(s)))
    except Exception as e:
        print(f"render_sessions error: {e}")
    return out


def capture_sessions() -> list[tuple[int, str, int]]:
    """(pid, process_name, state) for every session on the default microphone."""
    if not _available():
        return []
    try:
        mic = AudioUtilities.GetMicrophone()
    except Exception as e:
        print(f"GetMicrophone unavailable ({e}) — capture detection needs pycaw>=20240210")
        return []
    out = []
    try:
        mgr = mic.Activate(IAudioSessionManager2._iid_, comtypes.CLSCTX_ALL, None)
        mgr = mgr.QueryInterface(IAudioSessionManager2)
        enumr = mgr.GetSessionEnumerator()
        for i in range(enumr.GetCount()):
            ctl = enumr.GetSession(i)
            try:
                pid = ctl.QueryInterface(IAudioSessionControl2).GetProcessId()
            except Exception:
                pid = 0
            try:
                state = ctl.GetState()
            except Exception:
                state = -1
            out.append((pid, _proc_name(pid), state))
    except Exception as e:
        print(f"capture_sessions error: {e}")
    return out


def teams_meeting_active(cfg: dict) -> bool:
    """True if Teams holds an ACTIVE session on the configured endpoint."""
    method = cfg.get("teams_detect", {}).get("method", "mic")
    sessions = capture_sessions() if method == "mic" else render_sessions()
    return any(state == _ACTIVE and _is_teams(pid, name, cfg) for pid, name, state in sessions)


def _co_init():
    if comtypes is not None:
        try:
            comtypes.CoInitialize()
        except Exception:
            pass


def watch(cfg: dict) -> None:
    """Live diagnostic. Join a Teams call, watch the verdict flip, then leave."""
    if not _available():
        print("pycaw/comtypes not available — Windows only. Install: pip install pycaw comtypes")
        return
    _co_init()
    interval = cfg.get("teams_detect", {}).get("poll_interval_seconds", 2)
    method = cfg.get("teams_detect", {}).get("method", "mic")
    print(f"Watching audio sessions (verdict method = '{method}'). "
          f"Join a Teams call, then leave it. Ctrl+C to stop.\n")
    last = None
    while True:
        cap = capture_sessions()
        ren = render_sessions()
        verdict = teams_meeting_active(cfg)
        if verdict != last:
            print(f"\n>>> MEETING {'ACTIVE' if verdict else 'ENDED / IDLE'} <<<\n")
            last = verdict
        for tag, sess in (("MIC", cap), ("OUT", ren)):
            for pid, name, state in sess:
                is_t = _is_teams(pid, name, cfg)
                if is_t or state == _ACTIVE:
                    print(f"  {tag} pid={pid:<6} {name:<22} {_STATE_NAME.get(state, state):<9}"
                          f"{'  <-- TEAMS' if is_t else ''}")
        print("-" * 48)
        time.sleep(interval)


if __name__ == "__main__":
    from audio_transcriber.config import load_config
    watch(load_config())
