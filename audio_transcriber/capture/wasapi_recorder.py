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
