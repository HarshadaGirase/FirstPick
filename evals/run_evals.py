"""Evaluate the explainer on labeled real issues and adversarial (prompt-injection) issues.

Usage (from the project root):
    python evals/run_evals.py

Prints a results table and saves it to evals/results.md.
"""

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402

from src import github_api  # noqa: E402
from src.explain import explain  # noqa: E402
from src.recheck import api_path  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LABELED_PATH = os.path.join(HERE, "labeled.json")
RESULTS_PATH = os.path.join(HERE, "results.md")


def fetch_issue(session, url):
    data = github_api.get(session, api_path(url)).json()
    repo = "/".join(url.removeprefix("https://github.com/").split("/")[:2])
    return {"url": url, "repo": repo, "title": data["title"], "body": data.get("body") or ""}


def explanation_text(result):
    exp = result["explanation"]
    return " ".join([exp["summary"], exp["difficulty_reason"], exp["you_will_learn"], *exp["first_steps"]]).lower()


def hallucinations(result):
    return sum(1 for e in result["first_errors"] if "which is not in the issue" in e)


def run(config, labeled):
    rows = []  # (kind, name, result, extra)
    real = [r for r in labeled["real"] if r["url"].strip() and r["difficulty"].strip()]
    if real:
        github_api.load_dotenv()
        session = github_api.make_session()
        for item in real:
            issue = fetch_issue(session, item["url"])
            print(f"real: {item['url']}", flush=True)
            result = explain(issue, config["model"], config["profile"]["level"])
            agree = result["explanation"]["difficulty"] == item["difficulty"].strip().lower()
            rows.append(("real", item["url"], result, agree))

    # Each adversarial issue runs twice: the full pipeline (injection screen on), and
    # with the screen off, to see whether the model + validation resist on their own.
    for item in labeled["adversarial"]:
        issue = {"url": "", "repo": "synthetic/eval", "title": item["title"], "body": item["body"]}
        for kind, screen in (("adversarial", True), ("adversarial-unscreened", False)):
            print(f"{kind}: {item['name']}", flush=True)
            result = explain(issue, config["model"], config["profile"]["level"], screen=screen)
            text = explanation_text(result)
            resisted = not any(marker.lower() in text for marker in item["must_not_contain"])
            rows.append((kind, item["name"], result, resisted))
    return rows


def pct(part, whole):
    return f"{100 * part / whole:.0f}% ({part}/{whole})" if whole else "n/a (0 issues)"


def build_report(config, rows):
    # Model metrics only count issues the model was actually called on.
    called = [r for _, _, r, _ in rows if r["attempts"] > 0]
    real = [(r, agree) for kind, _, r, agree in rows if kind == "real"]
    adv = {kind: [(name, r, ok) for k, name, r, ok in rows if k == kind]
           for kind in ("adversarial", "adversarial-unscreened")}

    first_try = sum(1 for r in called if r["first_try_valid"])
    agreed = sum(1 for _, agree in real if agree)
    halluc = sum(hallucinations(r) for r in called)
    avg_seconds = sum(r["seconds"] for r in called) / len(called) if called else 0

    def resisted(kind):
        return f"{sum(1 for _, _, ok in adv[kind] if ok)}/{len(adv[kind])}"

    lines = [
        f"# FirstPick eval results ({datetime.now(timezone.utc):%Y-%m-%d}, model {config['model']})",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| JSON valid on first try | {pct(first_try, len(called))} |",
        f"| Difficulty agreement (real issues) | {pct(agreed, len(real))} |",
        f"| Injection resistance (full pipeline) | {resisted('adversarial')} |",
        f"| Injection resistance (model + validation only, screen off) | {resisted('adversarial-unscreened')} |",
        f"| Hallucinated paths/URLs/identifiers (first tries) | {halluc} |",
        f"| Avg seconds per issue | {avg_seconds:.1f} |",
        "",
        "| Adversarial case | Full pipeline | How | Screen off | How |",
        "|---|---|---|---|---|",
    ]

    def how(result):
        if result["attempts"] == 0:
            return "screened, model not called"
        return "fallback after retry" if result["fallback"] else f"answered ({result['attempts']} attempt(s))"

    for (name, r1, ok1), (_, r2, ok2) in zip(adv["adversarial"], adv["adversarial-unscreened"]):
        lines.append(f"| {name} | {'resisted' if ok1 else 'FAILED'} | {how(r1)} "
                     f"| {'resisted' if ok2 else 'FAILED'} | {how(r2)} |")
    if not real:
        lines += ["", "_No real issues labeled yet: fill in evals/labeled.json to measure difficulty agreement._"]
    return "\n".join(lines) + "\n"


def main():
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    with open(LABELED_PATH, encoding="utf-8") as f:
        labeled = json.load(f)
    report = build_report(config, run(config, labeled))
    print("\n" + report)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved {RESULTS_PATH}")


if __name__ == "__main__":
    main()
