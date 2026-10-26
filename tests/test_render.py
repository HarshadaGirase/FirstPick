from datetime import datetime, timezone

from src.render import escape, render_digest
from tests.helpers import load

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)
PROFILE = {"languages": ["Python"], "interests": ["LLMs", "NLP"], "level": "beginner"}
STATS = {"collected": 40, "dropped_closed": 1, "dropped_assigned": 2, "dropped_linked_pr": 3,
         "dropped_claimed": 4, "sent": 1, "model": "gemma3:4b", "seconds_per_issue": 12.5}
ISSUE = {
    "url": "https://github.com/huggingface/peft/issues/101",
    "repo": "huggingface/peft",
    "title": "Add type hints for @octocat in #123",
    "labels": ["good first issue"],
    "created_at": "2026-10-20T10:00:00Z",
    "comments": 2,
    "body": "Python helpers are missing type hints.",
}


def test_escape_wraps_mentions_in_backticks():
    assert escape("thanks @octocat!") == "thanks `@octocat`!"


def test_escape_wraps_issue_refs_in_backticks():
    assert escape("see #123 and huggingface/peft#45") == "see `#123` and `huggingface/peft#45`"


def test_escape_leaves_emails_alone():
    assert escape("mail me@example.com") == "mail me@example.com"


def test_escape_html_backticks_brackets_and_newlines():
    assert escape("<script>x</script>\n# heading `code` [link](u)") == \
        "&lt;script&gt;x&lt;/script&gt; # heading \\`code\\` \\[link\\](u)"


def test_digest_card_is_escaped_and_complete():
    result = {"explanation": load("explanation_valid.json"), "fallback": False}
    md = render_digest("2026-10-26", [(ISSUE, result)], STATS, PROFILE, NOW)

    assert "[Add type hints for `@octocat` in `#123`](https://github.com/huggingface/peft/issues/101)" in md
    assert "**Difficulty:** easy" in md
    assert "**Age:** 5 days" in md  # 5.6 days, counted in whole days
    assert "unassigned, no linked PR" in md
    assert "**Why it fits you:** mentions Python" in md
    assert "1. Fork the repo" in md
    assert "1 closed, 2 assigned, 3 with a linked PR, 4 claimed in comments" in md
    assert "@octocat" not in md.replace("`@octocat`", "")


def test_fallback_card_says_unavailable():
    result = {"explanation": {"summary": ISSUE["title"], "difficulty": "unknown"}, "fallback": True}
    md = render_digest("2026-10-26", [(ISSUE, result)], STATS, PROFILE, NOW)
    assert "Explanation unavailable" in md
    assert "First steps" not in md
