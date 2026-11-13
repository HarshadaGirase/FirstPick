"""Load and save state.json (the issue pool, sent and dropped URLs, and run stats)."""

import json
import os

STATE_PATH = "state.json"


def empty_state():
    # dropped: {url: reason} for issues the live recheck removed, so collect skips them.
    return {"pool": {}, "sent": [], "dropped": {}, "stats": []}


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
        json.dump(state, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def mark_sent(state, sent_urls, dropped):
    """Move sent issues to state.sent and dropped ones to state.dropped (dropped: {reason: [urls]})."""
    for url in sent_urls:
        state["pool"].pop(url, None)
        if url not in state["sent"]:
            state["sent"].append(url)
    for reason, urls in dropped.items():
        for url in urls:
            state["pool"].pop(url, None)
            state["dropped"][url] = reason
