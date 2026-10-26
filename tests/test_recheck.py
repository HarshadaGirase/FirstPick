from src import recheck
from src.recheck import drop_reason
from tests.helpers import load


def test_clean_issue_is_kept():
    assert drop_reason(load("issue_open.json"), load("timeline_clean.json"), load("comments_clean.json")) is None


def test_closed_issue_is_dropped():
    assert drop_reason(load("issue_closed.json"), [], []) == "closed"


def test_assigned_issue_is_dropped():
    assert drop_reason(load("issue_assigned.json"), [], []) == "assigned"


def test_cross_referenced_pull_request_is_dropped():
    assert drop_reason(load("issue_open.json"), load("timeline_pr.json"), []) == "linked_pr"


def test_cross_referenced_plain_issue_is_kept():
    # timeline_clean.json has a cross-reference from an issue, not a PR
    assert drop_reason(load("issue_open.json"), load("timeline_clean.json"), []) is None


def test_connected_event_is_dropped():
    assert drop_reason(load("issue_open.json"), [{"event": "connected"}], []) == "linked_pr"


def test_claim_comment_is_dropped():
    # uses a curly apostrophe: "I’d like to work on this"
    assert drop_reason(load("issue_open.json"), [], load("comments_claim.json")) == "claimed"


def test_claim_phrases_are_case_insensitive():
    comments = [{"body": "WORKING ON THIS now"}]
    assert drop_reason(load("issue_open.json"), [], comments) == "claimed"


def test_claim_older_than_last_10_comments_is_ignored():
    comments = [{"body": "assign me please"}] + [{"body": "any update?"}] * 10
    assert drop_reason(load("issue_open.json"), [], comments) is None


def test_api_path_from_issue_url():
    assert recheck.api_path("https://github.com/huggingface/peft/issues/101") == "/repos/huggingface/peft/issues/101"


def test_recheck_candidates_splits_survivors_and_drops(monkeypatch):
    reasons = {"https://x/1": None, "https://x/2": "closed", "https://x/3": "claimed"}
    monkeypatch.setattr(recheck, "recheck", lambda session, url: reasons[url])

    survivors, dropped = recheck.recheck_candidates(None, [{"url": u} for u in reasons])

    assert survivors == [{"url": "https://x/1"}]
    assert dropped == {"closed": ["https://x/2"], "assigned": [], "linked_pr": [], "claimed": ["https://x/3"]}
