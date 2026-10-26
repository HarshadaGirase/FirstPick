from datetime import datetime, timezone

from src import collect as collect_module
from src import github_api
from src.state import empty_state
from tests.helpers import load

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)
CONFIG = {
    "repos": ["huggingface/peft"],
    "labels": ["good first issue", "Good First Issue"],
    "profile": {"languages": ["Python"], "interests": ["LLMs"]},
    "max_age_days": 60,
}


def fake_search(monkeypatch, items):
    """Every search returns the same items (like case-insensitive label duplicates do)."""
    monkeypatch.setattr(github_api, "repo_exists", lambda session, repo: True)
    monkeypatch.setattr(github_api, "search_issues", lambda session, query: items)


def test_sent_issues_are_not_added_back(monkeypatch):
    issue = load("issue_open.json")
    fake_search(monkeypatch, [issue])
    state = empty_state()
    state["sent"].append(issue["html_url"])

    new = collect_module.collect(None, CONFIG, state, now=NOW)

    assert state["pool"] == {}
    assert new == {"huggingface/peft": 0}


def test_same_issue_from_two_labels_is_added_once(monkeypatch):
    fake_search(monkeypatch, [load("issue_open.json")])
    state = empty_state()

    new = collect_module.collect(None, CONFIG, state, now=NOW)

    assert list(state["pool"]) == ["https://github.com/huggingface/peft/issues/101"]
    assert new == {"huggingface/peft": 1}
    assert state["stats"][-1]["new_total"] == 1


def test_body_is_truncated(monkeypatch):
    issue = load("issue_open.json")
    issue["body"] = "x" * 5000
    fake_search(monkeypatch, [issue])
    state = empty_state()

    collect_module.collect(None, CONFIG, state, now=NOW)

    assert len(state["pool"][issue["html_url"]]["body"]) == 4000


def test_repo_that_404s_is_skipped(monkeypatch):
    monkeypatch.setattr(github_api, "repo_exists", lambda session, repo: False)
    assert collect_module.verify_repos(None, ["nobody/nothing"]) == []


def test_score_rewards_skill_and_freshness_and_penalises_comments():
    base = {"title": "Fix LLM tokenizer", "body": "Python code", "labels": [], "created_at": "2026-10-26T00:00:00Z", "comments": 0}
    old = dict(base, created_at="2026-08-01T00:00:00Z")
    busy = dict(base, comments=6)
    unrelated = dict(base, title="Fix CSS", body="")

    score = lambda issue: collect_module.score_issue(issue, CONFIG["profile"], 60, NOW)

    assert score(base) > score(old)
    assert score(base) > score(busy)
    assert score(base) > score(unrelated)
