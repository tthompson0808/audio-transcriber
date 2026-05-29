"""Canonical meeting writer. Handles dedup before insert."""
import json
import os
import re
import shutil
from datetime import datetime, timezone

from audio_transcriber.config import get_data_dir
from audio_transcriber.storage.index import add_to_index


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug[:50]


def save_meeting(meeting: dict, cfg: dict) -> str:
    """Write meeting JSON, then dedup-aware index update, then digest."""
    from audio_transcriber.capture.dedup import find_duplicate

    data_dir = get_data_dir(cfg)
    date = meeting.get("date", datetime.now().strftime("%Y-%m-%d"))
    month_dir = os.path.join(data_dir, "meetings", date[:7])
    os.makedirs(month_dir, exist_ok=True)

    title_slug = _slugify(meeting.get("title", "untitled"))
    start_time = (meeting.get("start_time") or "000000").replace(":", "")
    meeting_id = f"mtg_{date.replace('-', '')}_{start_time}"
    base_name = f"{date}_{title_slug}"

    existing_id = find_duplicate(meeting, cfg)
    if existing_id:
        print(f"Duplicate of {existing_id} — merging higher-fidelity source if applicable.")
        return _merge_into_existing(existing_id, meeting, cfg)

    canonical = {
        "schema_version": 1,
        "id": meeting_id,
        "source": meeting.get("source", "audio_transcriber"),
        "source_file": meeting.get("source_file"),
        "date": date,
        "start_time": meeting.get("start_time"),
        "end_time": meeting.get("end_time"),
        "duration_seconds": meeting.get("duration_seconds", 0),
        "title": meeting.get("title", "Untitled"),
        "app": meeting.get("app_name"),
        "participants": meeting.get("participants", []),
        "summary": meeting.get("summary", ""),
        "action_items": meeting.get("action_items", []),
        "utterances": meeting.get("utterances", []),
        "has_speakers": meeting.get("has_speakers", True),
        "tags": [],
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    json_path = os.path.join(month_dir, f"{base_name}.json")
    with open(json_path, "w") as f:
        json.dump(canonical, f, indent=2)

    audio_path = meeting.get("audio_path")
    if audio_path and os.path.exists(audio_path):
        dest = os.path.join(month_dir, f"{base_name}_audio.wav")
        shutil.copy2(audio_path, dest)

    vtt_path = meeting.get("vtt_path")
    if vtt_path and os.path.exists(vtt_path):
        dest = os.path.join(month_dir, f"{base_name}.vtt")
        shutil.copy2(vtt_path, dest)

    index_entry = {
        "id": meeting_id,
        "date": date,
        "title": meeting.get("title", "Untitled"),
        "source": meeting.get("source", "audio_transcriber"),
        "participants": meeting.get("participants", []),
        "path": f"{date[:7]}/{base_name}.json",
    }
    add_to_index(index_entry, cfg)

    try:
        from audio_transcriber.digest.pipeline import digest_meeting
        print("Running digest...")
        digest_meeting(meeting_id, cfg)
    except Exception as e:
        print(f"Digest failed (meeting saved OK): {e}")

    return json_path


# Source-fidelity ranking: higher index wins on merge.
_SOURCE_RANK = {
    "whisper_recording": 0,
    "whisper_dropzone": 1,
    "teams_paste": 2,
    "vtt_upload": 3,
    "graph_teams": 4,
}


def _merge_into_existing(existing_id: str, new: dict, cfg: dict) -> str:
    """Replace existing JSON if `new` has a higher-fidelity source."""
    from audio_transcriber.storage.index import load_index

    index = load_index(cfg)
    entry = next((m for m in index["meetings"] if m["id"] == existing_id), None)
    if not entry:
        return ""

    data_dir = get_data_dir(cfg)
    existing_path = os.path.join(data_dir, "meetings", entry["path"])
    with open(existing_path) as f:
        existing = json.load(f)

    new_rank = _SOURCE_RANK.get(new.get("source", ""), -1)
    old_rank = _SOURCE_RANK.get(existing.get("source", ""), -1)

    if new_rank <= old_rank:
        print(f"  → keeping existing source ({existing.get('source')}); new source ({new.get('source')}) is lower fidelity")
        return existing_path

    print(f"  → upgrading from {existing.get('source')} to {new.get('source')}")
    existing.update({
        "source": new.get("source"),
        "source_file": new.get("source_file"),
        "participants": new.get("participants", existing.get("participants", [])),
        "summary": new.get("summary") or existing.get("summary", ""),
        "action_items": new.get("action_items", existing.get("action_items", [])),
        "utterances": new.get("utterances", existing.get("utterances", [])),
        "has_speakers": new.get("has_speakers", existing.get("has_speakers", True)),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    })
    with open(existing_path, "w") as f:
        json.dump(existing, f, indent=2)

    try:
        from audio_transcriber.digest.pipeline import digest_meeting
        digest_meeting(existing_id, cfg)
    except Exception as e:
        print(f"Re-digest after merge failed: {e}")

    return existing_path


def search_transcripts(query: str, cfg: dict) -> list:
    data_dir = get_data_dir(cfg)
    meetings_dir = os.path.join(data_dir, "meetings")
    results = []
    if not os.path.exists(meetings_dir):
        return results
    query_lower = query.lower()
    for root, dirs, files in os.walk(meetings_dir):
        for fname in files:
            if not fname.endswith(".json") or fname == "index.json":
                continue
            filepath = os.path.join(root, fname)
            with open(filepath) as f:
                meeting = json.load(f)
            searchable = " ".join(
                u.get("text", "") for u in meeting.get("utterances", [])
            )
            searchable += " " + meeting.get("summary", "")
            searchable += " " + meeting.get("title", "")
            if query_lower in searchable.lower():
                idx = searchable.lower().index(query_lower)
                snippet_start = max(0, idx - 40)
                snippet_end = min(len(searchable), idx + len(query) + 40)
                snippet = searchable[snippet_start:snippet_end].replace("\n", " ")
                results.append({
                    "date": meeting.get("date", ""),
                    "title": meeting.get("title", fname),
                    "snippet": snippet,
                    "path": filepath,
                })
    return results
