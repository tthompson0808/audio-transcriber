"""Teams paste-text parser — ported verbatim from Tyler's AudioTools."""
import re


def _parse_teams_timestamp(text: str) -> str:
    h = m = s = 0
    h_match = re.search(r'(\d+)\s+hours?', text)
    m_match = re.search(r'(\d+)\s+minutes?', text)
    s_match = re.search(r'(\d+)\s+seconds?', text)
    if h_match: h = int(h_match.group(1))
    if m_match: m = int(m_match.group(1))
    if s_match: s = int(s_match.group(1))
    return f"{h:02d}:{m:02d}:{s:02d}"


def _detect_speakers(lines: list[str]) -> set[str]:
    speakers = set()
    for i, line in enumerate(lines):
        line = line.strip()
        if re.match(r'^[A-Z]{2,4}$', line):
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not re.match(r'^[A-Z]{2,4}$', next_line) and not re.match(r'^\d+\s+(minutes?|hours?)', next_line):
                    speakers.add(next_line)
    return speakers


def parse_teams_paste(text: str) -> list[dict]:
    lines = text.strip().splitlines()
    speakers = _detect_speakers(lines)
    utterances = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if not line or re.match(r'^[A-Z]{2,4}$', line) or "stopped transcription" in line.lower():
            i += 1
            continue

        if line in speakers:
            i += 1
            continue

        if re.match(r'^\d+\s+(minutes?|hours?)', line) and not any(line.startswith(s) for s in speakers):
            i += 1
            continue

        speaker_ts = None
        for s in speakers:
            if line.startswith(s + " "):
                remainder = line[len(s) + 1:]
                if re.search(r'\d+\s+(minutes?|hours?|seconds?)', remainder):
                    speaker_ts = (s, remainder)
                    break

        if speaker_ts:
            speaker, ts_text = speaker_ts
            timestamp = _parse_teams_timestamp(ts_text)

            i += 1
            if i < len(lines) and lines[i].strip():
                text_line = lines[i].strip()
                is_meta = (
                    text_line in speakers
                    or re.match(r'^[A-Z]{2,4}$', text_line)
                    or re.match(r'^\d+\s+(minutes?|hours?)', text_line)
                )
                if not is_meta:
                    utterances.append({
                        "speaker": speaker,
                        "start": timestamp,
                        "end": None,
                        "text": text_line,
                    })
            i += 1
            continue

        i += 1

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
