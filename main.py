"""FirstPick command-line entry point.

Usage:
    python main.py collect      # find new issues, add them to state.json
    python main.py send         # send the digest, if the schedule says it is due
    python main.py force-send   # send the digest now, ignoring the schedule
    python main.py dry-run      # build the digest into preview.md only; no delivery, no state changes
"""

import argparse
import os
from collections import Counter
from datetime import datetime, timezone

import yaml

from src import github_api
from src.collect import collect
from src.deliver import is_due, notify, write_digest
from src.explain import explain
from src.rank import top_candidates
from src.recheck import recheck_candidates
from src.render import render_digest
from src.state import load_state, mark_sent, save_state

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
    print(f"Rechecking {len(candidates)} candidates ...", flush=True)
    survivors, dropped = recheck_candidates(session, candidates)

    picks = []
    for issue in survivors[:config["top_n"]]:
        print(f"Explaining {issue['url']} ...", flush=True)
        result = explain(issue, config["model"], config["profile"]["level"])
        note = "FALLBACK: " + "; ".join(result["errors"]) if result["fallback"] else "ok"
        print(f"  {result['seconds']}s, {result['attempts']} attempt(s), {note}", flush=True)
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


def run_send(config, force=False):
    now = datetime.now(timezone.utc)
    if not force and not is_due(config["schedule"], now):
        print(f"Not due: schedule is weekly on {config['schedule']['send_day']} (UTC), today is {now:%A}.")
        return

    my_repo = os.environ.get("GITHUB_REPOSITORY")
    if not my_repo:
        raise SystemExit("GITHUB_REPOSITORY is not set (owner/repo of YOUR FirstPick repo).")
    branch = os.environ.get("GITHUB_REF_NAME", "main")

    session = github_api.make_session()
    state = load_state()
    markdown, picks, dropped, stats = build_digest(session, config, state, now)
    date = now.date().isoformat()
    digest_path = write_digest(date, markdown)
    print(f"Wrote {digest_path}")

    if picks:
        url = notify(session, my_repo, branch, digest_path, len(picks), date)
        print(f"Notification issue: {url}")
    else:
        print("No issues survived the recheck; no notification posted.")

    mark_sent(state, [issue["url"] for issue, _ in picks], dropped)
    state["stats"].append(stats)
    save_state(state)


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
    parser.add_argument("command", choices=["collect", "send", "force-send", "dry-run"])
    args = parser.parse_args()

    github_api.load_dotenv()
    config = load_config()
    if args.command == "collect":
        run_collect(config)
    elif args.command == "send":
        run_send(config)
    elif args.command == "force-send":
        run_send(config, force=True)
    elif args.command == "dry-run":
        run_dry_run(config)


if __name__ == "__main__":
    main()
