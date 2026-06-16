"""WASAPI loopback capture for Windows via pyaudiowpatch.

Captures whatever the speakers are playing (system audio) — works for any
meeting app without per-app integration. Writes a 16kHz mono WAV (good
enough for Whisper, ~1.92 MB/min).
"""
import os
import threading
import time
import wave
from datetime import datetime

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    pyaudio = None

_SAMPLE_RATE = 16000
_CHANNELS = 1
_FORMAT_WIDTH = 2  # 16-bit PCM


class WasapiRecorder:
    """Records the default WASAPI loopback device until stop() is called.

    Usage:
        rec = WasapiRecorder(out_path)
        rec.start()
        ...
        wav_path = rec.stop()
    """

    def __init__(self, out_path: str):
        if pyaudio is None:
            raise RuntimeError(
                "pyaudiowpatch not available. This module only runs on Windows. "
                "Install: pip install pyaudiowpatch"
            )
        self.out_path = out_path
        self._pa = None
        self._stream = None
        self._wav = None
        self._stop_event = threading.Event()
        self._thread = None
        self._started_at: datetime | None = None
        self._stopped_at: datetime | None = None

    def _open_loopback(self):
        self._pa = pyaudio.PyAudio()
        wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_out = self._pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        if not default_out.get("isLoopbackDevice", False):
            for loopback in self._pa.get_loopback_device_info_generator():
                if default_out["name"] in loopback["name"]:
                    default_out = loopback
                    break
            else:
                raise RuntimeError("No WASAPI loopback device found for default output.")

        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=_CHANNELS,
            rate=_SAMPLE_RATE,
            input=True,
            input_device_index=default_out["index"],
            frames_per_buffer=1024,
        )

    def _record_loop(self):
        self._wav = wave.open(self.out_path, "wb")
        self._wav.setnchannels(_CHANNELS)
        self._wav.setsampwidth(_FORMAT_WIDTH)
        self._wav.setframerate(_SAMPLE_RATE)
        while not self._stop_event.is_set():
            try:
                data = self._stream.read(1024, exception_on_overflow=False)
                self._wav.writeframes(data)
            except Exception as e:
                print(f"Recorder read error: {e}")
                break
        self._wav.close()
        self._stream.stop_stream()
        self._stream.close()
        self._pa.terminate()

    def start(self):
        os.makedirs(os.path.dirname(self.out_path) or ".", exist_ok=True)
        self._open_loopback()
        self._stop_event.clear()
        self._started_at = datetime.now()
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop(self) -> str:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self._stopped_at = datetime.now()
        return self.out_path

    @property
    def duration_seconds(self) -> int:
        if self._started_at and self._stopped_at:
            return int((self._stopped_at - self._started_at).total_seconds())
        if self._started_at:
            return int((datetime.now() - self._started_at).total_seconds())
        return 0


def new_recording_path(local_dir: str) -> str:
    os.makedirs(os.path.join(local_dir, "recordings"), exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(local_dir, "recordings", f"recording_{stamp}.wav")


# --------------------------------------------------------------------------- #
# Stereo capture: microphone (LEFT) + speaker loopback (RIGHT) in one WAV.
# Both streams are captured at their native rate, then resampled and combined
# at stop() — this avoids fragile real-time mixing and WASAPI sample-rate
# coercion. Channel separation lets us transcribe "me" vs "them" independently.
# --------------------------------------------------------------------------- #
try:
    import numpy as np
except ImportError:
    np = None


class _StreamWriter:
    """One WASAPI input stream → one temp WAV at the device's native format."""

    def __init__(self, pa, device_info: dict, tmp_path: str):
        self._pa = pa
        self.tmp_path = tmp_path
        self.rate = int(device_info.get("defaultSampleRate", 48000))
        self.channels = min(2, int(device_info.get("maxInputChannels", 1))) or 1
        self._stream = pa.open(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.rate,
            input=True,
            input_device_index=device_info["index"],
            frames_per_buffer=1024,
        )
        self._wav = wave.open(tmp_path, "wb")
        self._wav.setnchannels(self.channels)
        self._wav.setsampwidth(2)
        self._wav.setframerate(self.rate)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self._wav.writeframes(self._stream.read(1024, exception_on_overflow=False))
            except Exception as e:
                print(f"Stream read error ({os.path.basename(self.tmp_path)}): {e}")
                break

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=10)
        try:
            self._stream.stop_stream(); self._stream.close()
        finally:
            self._wav.close()


class DualStreamRecorder:
    """Record mic + speaker-loopback simultaneously into one 16 kHz stereo WAV.

    LEFT  channel = microphone  (the laptop owner)
    RIGHT channel = loopback    (everyone else in the meeting)

    Degrades gracefully: if only one source opens, writes a mono WAV and reports
    which side is missing. `levels` (set after stop) gives per-channel RMS so a
    caller can verify both sides actually carried signal.
    """

    def __init__(self, out_path: str, cfg: dict):
        if pyaudio is None:
            raise RuntimeError("pyaudiowpatch not available. Windows only. pip install pyaudiowpatch")
        if np is None:
            raise RuntimeError("numpy not available. pip install numpy")
        self.out_path = out_path
        self.cfg = cfg.get("capture", {})
        self.target_rate = int(self.cfg.get("target_sample_rate", 16000))
        self._pa = None
        self._mic = None
        self._loop = None
        self._started_at = None
        self._stopped_at = None
        self.levels = {"left_rms": 0.0, "right_rms": 0.0, "channels": 0}

    def _resolve_devices(self):
        from audio_transcriber.capture import audio_devices as ad
        mic_idx = self.cfg.get("mic_device_index")
        loop_idx = self.cfg.get("loopback_device_index")
        mic = self._pa.get_device_info_by_index(mic_idx) if mic_idx is not None else ad.find_default_mic(self._pa)
        loop = self._pa.get_device_info_by_index(loop_idx) if loop_idx is not None else ad.find_default_loopback(self._pa)
        return mic, loop

    def start(self):
        os.makedirs(os.path.dirname(self.out_path) or ".", exist_ok=True)
        self._pa = pyaudio.PyAudio()
        mic, loop = self._resolve_devices()
        base = os.path.splitext(self.out_path)[0]
        if mic:
            try:
                self._mic = _StreamWriter(self._pa, mic, base + "_mic.tmp.wav")
                self._mic.start()
            except Exception as e:
                print(f"! Mic stream failed to open ({mic.get('name')}): {e}")
        else:
            print("! No microphone resolved — owner's voice will not be captured.")
        if loop:
            try:
                self._loop = _StreamWriter(self._pa, loop, base + "_loop.tmp.wav")
                self._loop.start()
            except Exception as e:
                print(f"! Loopback stream failed to open ({loop.get('name')}): {e}")
        else:
            print("! No loopback resolved — remote participants will not be captured.")
        if not self._mic and not self._loop:
            self._pa.terminate()
            raise RuntimeError("Neither mic nor loopback could be opened — check `devices` output.")
        self._started_at = datetime.now()

    def stop(self) -> str:
        if self._mic:
            self._mic.stop()
        if self._loop:
            self._loop.stop()
        self._stopped_at = datetime.now()
        if self._pa:
            self._pa.terminate()

        left = _read_wav_mono(self._mic.tmp_path) if self._mic else None
        right = _read_wav_mono(self._loop.tmp_path) if self._loop else None
        _write_combined(left, right, self.out_path, self.target_rate, self.levels)

        for w in (self._mic, self._loop):
            if w and os.path.exists(w.tmp_path):
                try:
                    os.remove(w.tmp_path)
                except OSError:
                    pass
        return self.out_path

    @property
    def duration_seconds(self) -> int:
        if self._started_at and self._stopped_at:
            return int((self._stopped_at - self._started_at).total_seconds())
        if self._started_at:
            return int((datetime.now() - self._started_at).total_seconds())
        return 0


def _read_wav_mono(path: str):
    """Load a WAV → (mono float32 in [-1,1], sample_rate). Downmixes if needed."""
    if not path or not os.path.exists(path):
        return None
    with wave.open(path, "rb") as w:
        rate = w.getframerate()
        ch = w.getnchannels()
        raw = w.readframes(w.getnframes())
    if not raw:
        return (np.zeros(0, dtype=np.float32), rate)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        samples = samples.reshape(-1, ch).mean(axis=1)
    return (samples, rate)


def _resample(x, src_rate: int, dst_rate: int):
    if src_rate == dst_rate or len(x) == 0:
        return x
    n_out = int(round(len(x) * dst_rate / src_rate))
    if n_out <= 0:
        return np.zeros(0, dtype=np.float32)
    src_idx = np.linspace(0, len(x) - 1, num=n_out)
    return np.interp(src_idx, np.arange(len(x)), x).astype(np.float32)


def _rms(x) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


def _write_combined(left, right, out_path: str, target_rate: int, levels: dict) -> None:
    """Resample both sides to target_rate and write a stereo (or mono) 16-bit WAV."""
    l = _resample(left[0], left[1], target_rate) if left else None
    r = _resample(right[0], right[1], target_rate) if right else None

    if l is not None and r is not None:
        n = max(len(l), len(r))
        l = np.pad(l, (0, n - len(l)))
        r = np.pad(r, (0, n - len(r)))
        levels.update(left_rms=_rms(l), right_rms=_rms(r), channels=2)
        interleaved = np.empty(n * 2, dtype=np.float32)
        interleaved[0::2] = l
        interleaved[1::2] = r
        nch = 2
    else:
        mono = l if l is not None else r
        mono = mono if mono is not None else np.zeros(0, dtype=np.float32)
        levels.update(left_rms=_rms(l) if l is not None else 0.0,
                      right_rms=_rms(r) if r is not None else 0.0,
                      channels=1)
        interleaved = mono
        nch = 1

    pcm = np.clip(interleaved, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(2)
        w.setframerate(target_rate)
        w.writeframes(pcm.tobytes())
