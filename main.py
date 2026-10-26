"""FirstPick command-line entry point.

Usage:
    python main.py collect
    python main.py dry-run
"""

import argparse
from collections import Counter
from datetime import datetime, timezone

import yaml

from src import github_api
from src.collect import collect
from src.explain import explain
from src.rank import top_candidates
from src.recheck import recheck_candidates
from src.render import render_digest
from src.state import load_state, save_state

PREVIEW_PATH = "preview.md"


def load_config(path="config.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_collect(config):
    session = github_api.make_session()
    state = load_state()
    new_per_repo = collect(session, config, state)
    save_state(state)

    pool_per_repo = Counter(issue["repo"] for issue in state["pool"].values())
    print(f"\n{'repo':<28} {'new':>5} {'in pool':>8}")
    for repo in config["repos"]:
        print(f"{repo:<28} {new_per_repo.get(repo, 0):>5} {pool_per_repo.get(repo, 0):>8}")
    print(f"{'TOTAL':<28} {sum(new_per_repo.values()):>5} {len(state['pool']):>8}")


def build_digest(session, config, state, now):
    """Send pipeline up to the rendered digest: rank -> recheck -> explain -> render.

    Returns (markdown, picks, dropped, stats). Does not change state.
    """
    candidates = top_candidates(state["pool"], config["recheck_pool"])
    print(f"Rechecking {len(candidates)} candidates ...")
    survivors, dropped = recheck_candidates(session, candidates)

    picks = []
    for issue in survivors[:config["top_n"]]:
        print(f"Explaining {issue['url']} ...")
        result = explain(issue, config["model"], config["profile"]["level"])
        note = "FALLBACK: " + "; ".join(result["errors"]) if result["fallback"] else "ok"
        print(f"  {result['seconds']}s, {result['attempts']} attempt(s), {note}")
        picks.append((issue, result))

    total_seconds = sum(result["seconds"] for _, result in picks)
    stats = {
        "command": "send",
        "time": now.isoformat(timespec="seconds"),
        "collected": len(state["pool"]),
        **{f"dropped_{reason}": len(urls) for reason, urls in dropped.items()},
        "sent": len(picks),
        "model": config["model"],
        "seconds_per_issue": round(total_seconds / len(picks), 2) if picks else 0,
    }
    markdown = render_digest(now.date().isoformat(), picks, stats, config["profile"], now)
    return markdown, picks, dropped, stats


def run_dry_run(config):
    session = github_api.make_session()
    state = load_state()
    now = datetime.now(timezone.utc)
    markdown, _, _, _ = build_digest(session, config, state, now)
    with open(PREVIEW_PATH, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"\nWrote {PREVIEW_PATH} (state.json unchanged, nothing delivered)")


def main():
    parser = argparse.ArgumentParser(description="FirstPick: beginner-friendly AI repo issues")
    parser.add_argument("command", choices=["collect", "dry-run"])
    args = parser.parse_args()

    github_api.load_dotenv()
    config = load_config()
    if args.command == "collect":
        run_collect(config)
    elif args.command == "dry-run":
        run_dry_run(config)


if __name__ == "__main__":
    main()
