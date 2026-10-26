"""Render the digest markdown. All issue and model text is escaped first."""

import html
import re
from datetime import datetime

from src.collect import matched_terms

# @username, #123 and owner/repo#123 would ping people or link issues on GitHub.
MENTION_RE = re.compile(r"(?<![\w`])@[A-Za-z0-9][A-Za-z0-9-]*")
ISSUE_REF_RE = re.compile(r"(?<![\w`])(?:[\w.-]+/[\w.-]+)?#\d+\b")


def escape(text):
    """Make untrusted text safe to put in markdown.

    - collapses newlines, so text cannot start new headings or list items
    - escapes HTML, backticks and square brackets
    - wraps @username and #123 in backticks, so GitHub does not ping or link them
    """
    text = " ".join(str(text).split())
    text = html.escape(text, quote=False)
    text = text.replace("`", "\\`").replace("[", "\\[").replace("]", "\\]")
    text = MENTION_RE.sub(lambda m: f"`{m.group(0)}`", text)
    return ISSUE_REF_RE.sub(lambda m: f"`{m.group(0)}`", text)


def why_it_fits(issue, profile):
    matched = matched_terms(issue, profile)
    reason = f"mentions {', '.join(matched)}" if matched else "no direct profile match"
    labels = ", ".join(issue["labels"])
    return f"{reason}; labeled {labels}; suited to a {profile.get('level', 'beginner')}"


def age_days(issue, now):
    created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
    return (now - created).days


def render_card(number, issue, result, profile, now):
    exp = result["explanation"]
    lines = [
        f"## {number}. [{escape(issue['title'])}]({issue['url']})",
        "",
        f"**Repo:** {escape(issue['repo'])} · **Difficulty:** {escape(exp['difficulty'])}"
        f" · **Age:** {age_days(issue, now)} days · **Comments:** {issue['comments']}"
        " · unassigned, no linked PR",
        "",
        f"**Summary:** {escape(exp['summary'])}",
        "",
    ]
    if result["fallback"]:
        lines += ["_Explanation unavailable for this issue._", ""]
    else:
        lines += [
            f"**Why it's {escape(exp['difficulty'])}:** {escape(exp['difficulty_reason'])}",
            "",
            f"**Why it fits you:** {escape(why_it_fits(issue, profile))}",
            "",
            f"**What you'll learn:** {escape(exp['you_will_learn'])}",
            "",
            "**First steps:**",
            "",
        ]
        lines += [f"{i}. {escape(step)}" for i, step in enumerate(exp["first_steps"], 1)]
        lines.append("")
    return lines


def render_digest(date, picks, stats, profile, now):
    """picks: list of (pool issue, explain() result). Returns the markdown text."""
    lines = [f"# 🦥 FirstPick: {len(picks)} issues for {date}", ""]
    if not picks:
        lines += ["No open, unclaimed beginner issues this time.", ""]
    for number, (issue, result) in enumerate(picks, 1):
        lines += render_card(number, issue, result, profile, now)
        lines += ["---", ""]

    lines += [
        "### Stats",
        "",
        f"- Issues in pool: {stats['collected']}",
        f"- Dropped: {stats['dropped_closed']} closed, {stats['dropped_assigned']} assigned, "
        f"{stats['dropped_linked_pr']} with a linked PR, {stats['dropped_claimed']} claimed in comments",
        f"- Sent: {stats['sent']}",
        f"- Model: {escape(stats['model'])}, {stats['seconds_per_issue']} s per issue",
        "",
    ]
    return "\n".join(lines)
