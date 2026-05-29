"""Watch the OneDrive Drop_Recordings/ and Drop_Transcripts/ folders.

File-stability gate: wait until the file size has been unchanged for
N seconds (default 10) before processing. Prevents picking up a file
mid-OneDrive sync.
"""
import os
import time
from pathlib import Path

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    FileSystemEventHandler = object
    Observer = None


AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".mp4", ".m4v", ".mov"}
TRANSCRIPT_EXTS = {".vtt", ".md", ".txt"}
_STABILITY_SECONDS = 10
_STABILITY_POLL = 1


def _wait_until_stable(path: str, timeout: int = 300) -> bool:
    """Return True once the file size is unchanged for _STABILITY_SECONDS."""
    deadline = time.time() + timeout
    last_size = -1
    stable_since = None
    while time.time() < deadline:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size == last_size:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= _STABILITY_SECONDS:
                return True
        else:
            last_size = size
            stable_since = None
        time.sleep(_STABILITY_POLL)
    return False


class _DropHandler(FileSystemEventHandler):
    def __init__(self, on_audio, on_transcript):
        super().__init__()
        self.on_audio = on_audio
        self.on_transcript = on_transcript

    def on_created(self, event):
        if event.is_directory:
            return
        path = event.src_path
        ext = Path(path).suffix.lower()
        if ext in AUDIO_EXTS:
            self._process(path, self.on_audio)
        elif ext in TRANSCRIPT_EXTS:
            self._process(path, self.on_transcript)

    def _process(self, path: str, callback) -> None:
        print(f"Drop detected: {path} — waiting for sync to stabilize…")
        if not _wait_until_stable(path):
            print(f"  → timeout waiting for stability, skipping {path}")
            return
        try:
            callback(path)
        except Exception as e:
            print(f"Drop handler failed for {path}: {e}")


def start_watching(recordings_dir: str, transcripts_dir: str, on_audio, on_transcript):
    """Returns the Observer so caller can .stop()/.join() at shutdown."""
    if Observer is None:
        raise RuntimeError("watchdog not installed. pip install watchdog")
    os.makedirs(recordings_dir, exist_ok=True)
    os.makedirs(transcripts_dir, exist_ok=True)
    handler = _DropHandler(on_audio, on_transcript)
    observer = Observer()
    observer.schedule(handler, recordings_dir, recursive=False)
    observer.schedule(handler, transcripts_dir, recursive=False)
    observer.start()
    print(f"Watching {recordings_dir} and {transcripts_dir}")
    return observer
