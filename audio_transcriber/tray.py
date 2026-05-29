"""System tray icon for the CEO.

States:
  gray  — idle, no recording
  red   — actively recording
  yellow — uploading/transcribing/synthesizing

Right-click menu:
  Open Dashboard · Stop Recording · Pause Auto-Capture · Quit
"""
import os
import sys
import threading
import time
import webbrowser

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None

from audio_transcriber.config import load_config
from audio_transcriber.capture import meeting as meeting_mod


STATE_IDLE = "idle"
STATE_RECORDING = "recording"
STATE_PROCESSING = "processing"

_COLORS = {
    STATE_IDLE: (148, 163, 184),       # slate-400
    STATE_RECORDING: (220, 38, 38),    # red-600
    STATE_PROCESSING: (234, 179, 8),   # yellow-500
}


def _make_icon(state: str):
    if Image is None:
        return None
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 56, 56), fill=_COLORS[state])
    return img


class TrayApp:
    def __init__(self):
        self.cfg = load_config()
        self.state = STATE_IDLE
        self.paused = False
        self.icon = None

    def _open_dashboard(self, icon=None, item=None):
        dash = self.cfg.get("dashboard", {})
        webbrowser.open(f"http://{dash.get('host', '127.0.0.1')}:{dash.get('port', 8765)}/")

    def _stop_recording(self, icon=None, item=None):
        result = meeting_mod.stop(self.cfg)
        self._set_state(STATE_IDLE)
        print(result)

    def _toggle_pause(self, icon=None, item=None):
        self.paused = not self.paused
        if self.icon:
            self.icon.update_menu()

    def _quit(self, icon=None, item=None):
        if self.icon:
            self.icon.stop()
        sys.exit(0)

    def _menu(self):
        return pystray.Menu(
            pystray.MenuItem("Open Dashboard", self._open_dashboard, default=True),
            pystray.MenuItem(
                "Stop Recording",
                self._stop_recording,
                enabled=lambda item: self.state == STATE_RECORDING,
            ),
            pystray.MenuItem(
                lambda item: "Resume Auto-Capture" if self.paused else "Pause Auto-Capture",
                self._toggle_pause,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

    def _watch_state_file(self):
        """Poll meeting state file every 2s and update icon."""
        while True:
            try:
                state = meeting_mod.status(self.cfg)
                new_state = STATE_RECORDING if state.get("active") else STATE_IDLE
                if new_state != self.state:
                    self._set_state(new_state)
            except Exception as e:
                print(f"State poll error: {e}")
            time.sleep(2)

    def _set_state(self, state: str):
        self.state = state
        if self.icon:
            self.icon.icon = _make_icon(state)
            self.icon.title = f"Audio_Transcriber — {state}"

    def run(self):
        if pystray is None:
            raise RuntimeError("pystray + Pillow not installed. pip install pystray pillow")
        self.icon = pystray.Icon(
            "audio_transcriber",
            icon=_make_icon(STATE_IDLE),
            title="Audio_Transcriber — idle",
            menu=self._menu(),
        )
        watcher = threading.Thread(target=self._watch_state_file, daemon=True)
        watcher.start()
        self.icon.run()


def main():
    TrayApp().run()


if __name__ == "__main__":
    main()
