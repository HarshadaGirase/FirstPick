from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src import deliver, github_api
from src.deliver import is_due, notification_body, write_digest

SUNDAY = datetime(2026, 11, 1, 13, 30, tzinfo=timezone.utc)
MONDAY = datetime(2026, 11, 2, 13, 30, tzinfo=timezone.utc)
MY_REPO = "HarshadaGirase/FirstPick"


def test_daily_is_always_due():
    assert is_due({"mode": "daily", "send_day": "sunday"}, MONDAY)


def test_weekly_is_due_only_on_send_day():
    weekly = {"mode": "weekly", "send_day": "Sunday"}
    assert is_due(weekly, SUNDAY)
    assert not is_due(weekly, MONDAY)


def test_bad_schedule_mode_raises():
    with pytest.raises(ValueError):
        is_due({"mode": "hourly", "send_day": "sunday"}, MONDAY)


def test_write_digest(tmp_path):
    path = write_digest("2026-11-02", "# hi\n", folder=str(tmp_path))
    assert path.endswith("2026-11-02.md")
    assert open(path).read() == "# hi\n"


def test_notification_links_only_to_my_digest():
    body = notification_body(MY_REPO, "main", "digests/2026-11-02.md", 5, "2026-11-02")
    assert f"https://github.com/{MY_REPO}/blob/main/digests/2026-11-02.md" in body
    assert "@" not in body
    assert "huggingface" not in body


def test_notification_refuses_links_outside_my_repo():
    with pytest.raises(ValueError):
        deliver._check_safe("see https://github.com/huggingface/peft/issues/1", MY_REPO)
    with pytest.raises(ValueError):
        deliver._check_safe("thanks @someone", MY_REPO)


def test_notify_creates_one_issue_in_my_repo_and_closes_previous(monkeypatch):
    calls = []

    def fake_request(session, method, path, params=None, json=None):
        calls.append((method, path, json))
        if method == "GET" and path.endswith(f"/labels/{deliver.LABEL}"):
            raise github_api.GitHubError("not found", status=404)
        if method == "GET":  # open notifications: one old one plus a PR to ignore
            return SimpleNamespace(json=lambda: [{"number": 3}, {"number": 4, "pull_request": {}}], links={})
        return SimpleNamespace(json=lambda: {"html_url": f"https://github.com/{MY_REPO}/issues/9"})

    monkeypatch.setattr(github_api, "request", fake_request)
    url = deliver.notify(None, MY_REPO, "main", "digests/2026-11-02.md", 5, "2026-11-02")

    assert url == f"https://github.com/{MY_REPO}/issues/9"
    writes = [(m, p) for m, p, _ in calls if m != "GET"]
    assert writes == [
        ("POST", f"/repos/{MY_REPO}/labels"),           # label was missing, so create it
        ("POST", f"/repos/{MY_REPO}/issues"),           # the ONE new notification
        ("PATCH", f"/repos/{MY_REPO}/issues/3"),        # close the previous one (not the PR)
    ]
    assert all(p.startswith(f"/repos/{MY_REPO}/") for _, p, _ in calls)  # never touches upstream
    new_issue = calls[[p for _, p, _ in calls].index(f"/repos/{MY_REPO}/issues")][2]
    assert new_issue["title"] == "🦥 FirstPick: 5 issues for 2026-11-02"
    assert new_issue["labels"] == ["firstpick"]
