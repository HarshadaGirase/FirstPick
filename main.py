"""FirstPick command-line entry point.

Usage:
    python main.py collect
"""

import argparse
from collections import Counter

import yaml

from src import github_api
from src.collect import collect
from src.state import load_state, save_state


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


def main():
    parser = argparse.ArgumentParser(description="FirstPick: beginner-friendly AI repo issues")
    parser.add_argument("command", choices=["collect"])
    args = parser.parse_args()

    github_api.load_dotenv()
    config = load_config()
    if args.command == "collect":
        run_collect(config)


if __name__ == "__main__":
    main()
