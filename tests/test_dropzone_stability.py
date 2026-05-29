"""OneDrive stability check — _wait_until_stable should wait for file size
to stop changing before letting the watcher process the file.
"""
import threading
import time

from audio_transcriber.capture.dropzone_watcher import _wait_until_stable


def test_wait_until_stable_returns_true_for_static_file(tmp_path):
    f = tmp_path / "static.bin"
    f.write_bytes(b"x" * 1024)
    # Stability check waits 10s by default; the test patches it tighter.
    import audio_transcriber.capture.dropzone_watcher as dw
    original = dw._STABILITY_SECONDS
    dw._STABILITY_SECONDS = 1
    try:
        start = time.time()
        assert _wait_until_stable(str(f), timeout=10)
        elapsed = time.time() - start
        assert elapsed >= 1
    finally:
        dw._STABILITY_SECONDS = original


def test_wait_until_stable_waits_for_growing_file(tmp_path):
    f = tmp_path / "growing.bin"
    f.write_bytes(b"x" * 100)

    import audio_transcriber.capture.dropzone_watcher as dw
    original = dw._STABILITY_SECONDS
    dw._STABILITY_SECONDS = 1

    def grow():
        for i in range(3):
            time.sleep(0.6)
            with open(f, "ab") as handle:
                handle.write(b"y" * 200)

    t = threading.Thread(target=grow)
    t.start()
    try:
        start = time.time()
        ok = _wait_until_stable(str(f), timeout=10)
        elapsed = time.time() - start
        t.join()
        assert ok
        # Should have waited at least until growth stopped + the stability window
        assert elapsed >= 2.0
    finally:
        dw._STABILITY_SECONDS = original
