"""WASAPI device enumeration — the first thing to run on a new machine.

`pyaudiowpatch` exposes two kinds of inputs we care about:
  - real **capture** devices (the microphone)
  - **loopback** devices (a mirror of an output, so we can record what the
    speakers are playing = the remote meeting participants)

This module finds both, auto-picks sane defaults, and prints a human table so
we can confirm the right indices on the actual hardware before recording.
"""
try:
    import pyaudiowpatch as pyaudio
except ImportError:
    pyaudio = None  # importable on macOS for dev; real work needs Windows + pyaudiowpatch


def _require_pyaudio():
    if pyaudio is None:
        raise RuntimeError(
            "pyaudiowpatch not available. This runs on Windows only. "
            "Install: pip install pyaudiowpatch"
        )


def find_default_mic(pa) -> dict | None:
    """The default WASAPI input (microphone) device info, or None."""
    try:
        wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        idx = wasapi.get("defaultInputDevice", -1)
        if idx is not None and idx >= 0:
            return pa.get_device_info_by_index(idx)
    except Exception:
        pass
    try:
        return pa.get_default_input_device_info()
    except Exception:
        return None


def find_default_loopback(pa) -> dict | None:
    """The loopback device that mirrors the default output (= the speakers).

    Returns the loopback device whose name contains the default output name,
    falling back to the first loopback device found.
    """
    try:
        wasapi = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = pa.get_device_info_by_index(wasapi["defaultOutputDevice"])
    except Exception:
        default_out = None

    loopbacks = list(_iter_loopbacks(pa))
    if not loopbacks:
        return None
    if default_out:
        for lb in loopbacks:
            if default_out["name"] in lb["name"]:
                return lb
    return loopbacks[0]


def _iter_loopbacks(pa):
    """Yield every loopback device info. pyaudiowpatch-specific generator."""
    try:
        yield from pa.get_loopback_device_info_generator()
    except Exception:
        # Older/edge builds: scan all devices for the isLoopbackDevice flag.
        for i in range(pa.get_device_count()):
            try:
                info = pa.get_device_info_by_index(i)
                if info.get("isLoopbackDevice"):
                    yield info
            except Exception:
                continue


def list_devices() -> dict:
    """Structured snapshot: mics, loopbacks, and the auto-picked defaults."""
    _require_pyaudio()
    pa = pyaudio.PyAudio()
    try:
        mics = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0 and not info.get("isLoopbackDevice"):
                mics.append(info)
        loopbacks = list(_iter_loopbacks(pa))
        default_mic = find_default_mic(pa)
        default_loopback = find_default_loopback(pa)
        return {
            "mics": mics,
            "loopbacks": loopbacks,
            "default_mic": default_mic,
            "default_loopback": default_loopback,
        }
    finally:
        pa.terminate()


def _fmt(info: dict | None) -> str:
    if not info:
        return "  (none found)"
    return (f"  [{info['index']:>3}] {info['name']}  "
            f"({int(info.get('maxInputChannels', 0))}ch, "
            f"{int(info.get('defaultSampleRate', 0))} Hz)")


def print_devices() -> None:
    """Human diagnostic — run this on the target machine first."""
    snap = list_devices()
    print("=== Microphones (capture devices) ===")
    for m in snap["mics"]:
        print(_fmt(m))
    print("\n=== Loopback devices (mirror of an output = the speakers) ===")
    for lb in snap["loopbacks"]:
        print(_fmt(lb))
    print("\n=== Auto-picked defaults (what the recorder will use if indices are unset) ===")
    print("Mic (LEFT channel):")
    print(_fmt(snap["default_mic"]))
    print("Loopback (RIGHT channel):")
    print(_fmt(snap["default_loopback"]))
    if not snap["default_mic"]:
        print("\n! No default microphone found — stereo capture will fall back to loopback-only.")
    if not snap["default_loopback"]:
        print("\n! No loopback device found — check that the default output device is active.")


if __name__ == "__main__":
    print_devices()
