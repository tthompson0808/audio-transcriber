"""VTT parser — ported verbatim from Tyler's AudioTools."""
import re


def _parse_timestamp(ts: str) -> str:
    ts = ts.strip()
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        s = s.split(".")[0]
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    if len(parts) == 2:
        m, s = parts
        s = s.split(".")[0]
        return f"00:{int(m):02d}:{int(s):02d}"
    return None


def parse_vtt(text: str) -> list[dict]:
    lines = text.strip().splitlines()
    utterances = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if "-->" not in line:
            i += 1
            continue

        ts_match = re.match(r"([\d:.]+)\s*-->\s*([\d:.]+)", line)
        if not ts_match:
            i += 1
            continue

        start = _parse_timestamp(ts_match.group(1))
        end = _parse_timestamp(ts_match.group(2))

        i += 1
        text_lines = []
        while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
            text_lines.append(lines[i].strip())
            i += 1

        full_text = " ".join(text_lines)

        speaker = "Unknown"
        voice_match = re.match(r"<v\s+([^>]+)>(.+)", full_text)
        if voice_match:
            speaker = voice_match.group(1).strip()
            full_text = voice_match.group(2).strip()

        full_text = re.sub(r"</v>", "", full_text).strip()

        if full_text:
            utterances.append({
                "speaker": speaker,
                "start": start,
                "end": end,
                "text": full_text,
            })

    return utterances


def extract_participants(utterances: list[dict]) -> list[str]:
    seen = set()
    participants = []
    for u in utterances:
        name = u.get("speaker", "Unknown")
        if name != "Unknown" and name not in seen:
            seen.add(name)
            participants.append(name)
    return participants


def extract_date_from_filename(filename: str) -> str | None:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if match:
        return match.group(1)
    return None


def extract_start_time(utterances: list[dict]) -> str | None:
    for u in utterances:
        if u.get("start"):
            return u["start"]
    return None


def utterances_to_plain_text(utterances: list[dict]) -> str:
    lines = []
    for u in utterances:
        prefix = f"[{u['start']}] " if u.get("start") else ""
        speaker = u.get("speaker", "Unknown")
        lines.append(f"{prefix}{speaker}: {u['text']}")
    return "\n".join(lines)
