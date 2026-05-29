"""Meeting index — flat JSON registry of every meeting written."""
import json
import os

from audio_transcriber.config import get_data_dir


def _index_path(cfg: dict) -> str:
    return os.path.join(get_data_dir(cfg), "meetings", "index.json")


def load_index(cfg: dict) -> dict:
    path = _index_path(cfg)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"meetings": []}


def add_to_index(entry: dict, cfg: dict) -> None:
    idx = load_index(cfg)
    idx["meetings"] = [m for m in idx["meetings"] if m["id"] != entry["id"]]
    idx["meetings"].append(entry)
    idx["meetings"].sort(key=lambda m: m["date"])
    path = _index_path(cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(idx, f, indent=2)
