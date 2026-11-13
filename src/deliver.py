"""Deliver the digest: write digests/DATE.md and post ONE notification issue in MY repo.

Never spam maintainers: upstream issue links appear only in the digest file, and
nothing here ever touches an upstream repo.
"""

import os
import re

from src import github_api

DIGEST_DIR = "digests"
LABEL = "firstpick"
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def is_due(schedule, now):
    """daily: every run is due. weekly: only on send_day (UTC)."""
    mode = schedule["mode"]
    if mode == "daily":
        return True
    if mode == "weekly":
        send_day = schedule["send_day"].lower()
        if send_day not in DAYS:
            raise ValueError(f"schedule.send_day must be one of {DAYS}, got {schedule['send_day']!r}")
        return DAYS[now.weekday()] == send_day
    raise ValueError(f"schedule.mode must be 'daily' or 'weekly', got {mode!r}")


def write_digest(date, markdown, folder=DIGEST_DIR):
    os.makedirs(folder, exist_ok=True)
    path = f"{folder}/{date}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return path


def notification_title(count, date):
    return f"🦥 FirstPick: {count} issues for {date}"


def notification_body(my_repo, branch, digest_path, count, date):
    """Links ONLY to the digest in my repo: no upstream links, no @mentions."""
    link = f"https://github.com/{my_repo}/blob/{branch}/{digest_path}"
    body = (
        f"Your FirstPick digest for {date} is ready: {count} beginner-friendly issues, "
        "each re-checked live (open, unassigned, no linked PR, not claimed).\n\n"
        f"👉 [Read the digest]({link})\n\n"
        "_The previous FirstPick notification was closed automatically._\n"
    )
    _check_safe(body, my_repo)
    return body


def _check_safe(body, my_repo):
    """Refuse to post a body that could ping someone or link outside my repo."""
    if "@" in body:
        raise ValueError("notification body must not contain @")
    for url in re.findall(r"https?://\S+", body):
        if not url.startswith(f"https://github.com/{my_repo}/"):
            raise ValueError(f"notification body links outside {my_repo}: {url}")


def ensure_label(session, my_repo):
    if not github_api.exists(session, f"/repos/{my_repo}/labels/{LABEL}"):
        github_api.post(session, f"/repos/{my_repo}/labels",
                        {"name": LABEL, "color": "c5def5", "description": "FirstPick digest notifications"})


def open_notifications(session, my_repo):
    items = github_api.get_all(session, f"/repos/{my_repo}/issues?labels={LABEL}&state=open")
    return [i for i in items if "pull_request" not in i]


def notify(session, my_repo, branch, digest_path, count, date):
    """Create the new notification issue, then close the previous ones. Returns its URL."""
    ensure_label(session, my_repo)
    previous = open_notifications(session, my_repo)
    issue = github_api.post(session, f"/repos/{my_repo}/issues", {
        "title": notification_title(count, date),
        "body": notification_body(my_repo, branch, digest_path, count, date),
        "labels": [LABEL],
    }).json()
    for old in previous:
        github_api.patch(session, f"/repos/{my_repo}/issues/{old['number']}", {"state": "closed"})
    return issue["html_url"]
