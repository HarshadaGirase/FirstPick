"""Load and save state.json (the issue pool, sent URLs, and run stats)."""

import json
import os

STATE_PATH = "state.json"


def empty_state():
    return {"pool": {}, "sent": [], "stats": []}


def load_state(path=STATE_PATH):
    if not os.path.exists(path):
        return empty_state()
    with open(path, encoding="utf-8") as f:
        state = json.load(f)
    for key, default in empty_state().items():
        state.setdefault(key, default)
    return state


def save_state(state, path=STATE_PATH):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)
