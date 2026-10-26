"""Small wrapper around the GitHub REST API using requests."""

import os
import time

import requests

API = "https://api.github.com"
SEARCH_PAUSE_SECONDS = 1.0
MAX_RETRIES = 3


class GitHubError(Exception):
    pass


def load_dotenv(path=".env"):
    """Load KEY=VALUE lines from a local .env file into os.environ (if present)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def make_session():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubError("GITHUB_TOKEN is not set (put it in .env or the environment).")
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "FirstPick",
    })
    return session


def _wait_seconds(response):
    """How long GitHub asks us to wait, or None if this is not a rate-limit response."""
    if "Retry-After" in response.headers:
        return int(response.headers["Retry-After"])
    if response.headers.get("X-RateLimit-Remaining") == "0":
        reset = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
        return max(reset - int(time.time()), 0) + 1
    return None


def get(session, path, params=None):
    """GET a GitHub API path, waiting and retrying when rate limited."""
    url = path if path.startswith("http") else API + path
    for _ in range(MAX_RETRIES):
        response = session.get(url, params=params, timeout=30)
        if response.status_code in (403, 429):
            wait = _wait_seconds(response)
            if wait is not None:
                print(f"  rate limited, waiting {wait}s ...")
                time.sleep(wait)
                continue
        if response.status_code >= 400:
            raise GitHubError(f"GET {url} -> {response.status_code}: {response.text[:200]}")
        # Out of quota for this window: wait now so the next call succeeds.
        if response.headers.get("X-RateLimit-Remaining") == "0":
            wait = _wait_seconds(response)
            print(f"  rate limit used up, waiting {wait}s ...")
            time.sleep(wait)
        return response
    raise GitHubError(f"GET {url} still rate limited after {MAX_RETRIES} tries")


def repo_exists(session, full_name):
    """True if the repo exists; False on 404. Other errors are raised."""
    response = session.get(f"{API}/repos/{full_name}", timeout=30)
    if response.status_code == 404:
        return False
    if response.status_code >= 400:
        raise GitHubError(f"GET /repos/{full_name} -> {response.status_code}: {response.text[:200]}")
    return True


def search_issues(session, query, max_pages=10):
    """Return all issue items for a search query (up to 1000, GitHub's limit)."""
    items = []
    for page in range(1, max_pages + 1):
        time.sleep(SEARCH_PAUSE_SECONDS)
        response = get(session, "/search/issues", {"q": query, "per_page": 100, "page": page})
        data = response.json()
        items.extend(data["items"])
        if len(data["items"]) < 100:
            break
    return items
