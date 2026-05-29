"""Read the foreground window title for a target app — used for exclusion checks.

Reads Zoom's window title which usually contains the meeting topic.
"""
try:
    import pygetwindow as gw
except ImportError:
    gw = None


def get_titles_for_process(process_name: str) -> list[str]:
    """Return all window titles whose owning process matches `process_name`.

    pygetwindow doesn't expose PID-to-window mapping, so we fall back to
    substring matches on the title (Zoom puts "Zoom Meeting" in the title).
    """
    if gw is None:
        return []
    proc_root = process_name.replace(".exe", "").lower()
    matches = []
    try:
        for w in gw.getAllWindows():
            title = (w.title or "").strip()
            if not title:
                continue
            if proc_root in title.lower() or "zoom meeting" in title.lower():
                matches.append(title)
    except Exception:
        return []
    return matches


def get_meeting_title(process_name: str) -> str | None:
    """Best-effort meeting title from window titles. Returns None if unclear."""
    titles = get_titles_for_process(process_name)
    if not titles:
        return None
    for t in titles:
        if "Zoom Meeting" in t and t != "Zoom Meeting":
            return t.replace("Zoom Meeting", "").strip(" -·|")
    return titles[0]
