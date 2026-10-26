"""Re-check candidate issues live and drop ones someone has already taken."""

from src import github_api

CLAIM_PHRASES = [
    "i'd like to work on",
    "can i work on",
    "i'll take",
    "working on this",
    "assign me",
    "i am working",
]
COMMENTS_TO_CHECK = 10

# The reasons drop_reason() can return; send stats count each as dropped_<reason>.
REASONS = ["closed", "assigned", "linked_pr", "claimed"]


def api_path(issue_url):
    """https://github.com/o/r/issues/7 -> /repos/o/r/issues/7"""
    owner, repo, _, number = issue_url.removeprefix("https://github.com/").split("/")[:4]
    return f"/repos/{owner}/{repo}/issues/{number}"


def _is_claim(comment_body):
    text = (comment_body or "").lower().replace("’", "'")  # treat ’ like '
    return any(phrase in text for phrase in CLAIM_PHRASES)


def _has_linked_pr(timeline):
    for event in timeline:
        if event.get("event") == "connected":
            return True
        if event.get("event") == "cross-referenced":
            source_issue = (event.get("source") or {}).get("issue") or {}
            if "pull_request" in source_issue:
                return True
    return False


def drop_reason(issue, timeline, comments):
    """Why this issue should be dropped (one of REASONS), or None to keep it.

    issue, timeline and comments are the raw GitHub API JSON for one issue.
    """
    if issue["state"] != "open":
        return "closed"
    if issue.get("assignees"):
        return "assigned"
    if _has_linked_pr(timeline):
        return "linked_pr"
    if any(_is_claim(c.get("body")) for c in comments[-COMMENTS_TO_CHECK:]):
        return "claimed"
    return None


def recheck(session, issue_url):
    """Fetch the issue, its timeline and comments live, and return drop_reason()."""
    path = api_path(issue_url)
    issue = github_api.get(session, path).json()
    timeline = github_api.get_all(session, path + "/timeline")
    comments = github_api.get_all(session, path + "/comments") if issue["comments"] else []
    return drop_reason(issue, timeline, comments)


def recheck_candidates(session, candidates):
    """Recheck each candidate. Returns (survivors, {reason: [urls dropped]})."""
    survivors = []
    dropped = {reason: [] for reason in REASONS}
    for candidate in candidates:
        reason = recheck(session, candidate["url"])
        if reason:
            print(f"  drop ({reason}): {candidate['url']}")
            dropped[reason].append(candidate["url"])
        else:
            survivors.append(candidate)
    return survivors, dropped
