"""Collect open, unassigned beginner issues into state.pool and score them."""

from datetime import datetime, timedelta, timezone

from src import github_api

BODY_LIMIT = 4000


def verify_repos(session, repos):
    """Return the repos that exist; warn about any that 404."""
    found = []
    for repo in repos:
        if github_api.repo_exists(session, repo):
            found.append(repo)
        else:
            print(f"WARNING: repo {repo} not found (404), skipping")
    return found


def build_query(repo, label, since_date):
    return f'repo:{repo} is:issue is:open no:assignee label:"{label}" created:>={since_date}'


def to_pool_entry(item, repo, now):
    return {
        "url": item["html_url"],
        "title": item["title"],
        "repo": repo,
        "labels": [label["name"] for label in item["labels"]],
        "created_at": item["created_at"],
        "comments": item["comments"],
        "body": (item.get("body") or "")[:BODY_LIMIT],
        "first_seen": now.isoformat(timespec="seconds"),
    }


def _terms(profile):
    """Lowercase match terms from the profile; 'LLMs' also matches 'llm'."""
    terms = set()
    for word in profile.get("languages", []) + profile.get("interests", []):
        word = word.lower()
        terms.add(word)
        if word.endswith("s"):
            terms.add(word[:-1])
    return terms


def score_issue(issue, profile, max_age_days, now):
    """Higher is better: +1 per profile term matched, up to +3 for freshness, -0.5 per comment."""
    text = " ".join([issue["title"], issue["body"], " ".join(issue["labels"])]).lower()
    skill = sum(1 for term in _terms(profile) if term in text)

    created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
    age_days = (now - created).days
    freshness = 3 * max(0, max_age_days - age_days) / max_age_days

    return round(skill + freshness - 0.5 * issue["comments"], 2)


def collect(session, config, state, now=None):
    """Search every repo/label, add new issues to the pool, rescore. Returns new-issue counts per repo."""
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=config["max_age_days"])).date().isoformat()
    sent = set(state["sent"])
    pool = state["pool"]

    repos = verify_repos(session, config["repos"])
    new_per_repo = {}
    for repo in repos:
        new_count = 0
        for label in config["labels"]:
            for item in github_api.search_issues(session, build_query(repo, label, since)):
                url = item["html_url"]
                if url in sent or url in pool:
                    continue
                pool[url] = to_pool_entry(item, repo, now)
                new_count += 1
        new_per_repo[repo] = new_count

    for issue in pool.values():
        issue["score"] = score_issue(issue, config["profile"], config["max_age_days"], now)

    state["stats"].append({
        "command": "collect",
        "time": now.isoformat(timespec="seconds"),
        "new_per_repo": new_per_repo,
        "new_total": sum(new_per_repo.values()),
        "pool_size": len(pool),
    })
    return new_per_repo
