"""Small wrapper around the GitHub REST API using requests."""

import os
import time

import requests

API = "https://api.github.com"
# Search allows 30 requests/minute; 1s gaps kept tripping the secondary rate limit.
SEARCH_PAUSE_SECONDS = 2.5
MAX_RETRIES = 3


class GitHubError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


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


def _wait_seconds(response, attempt=1):
    """How long GitHub asks us to wait, or None if this is not a rate-limit response."""
    if "Retry-After" in response.headers:
        return int(response.headers["Retry-After"])
    if response.headers.get("X-RateLimit-Remaining") == "0":
        reset = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
        return max(reset - int(time.time()), 0) + 1
    # Secondary rate limits may send neither header; GitHub says wait at least a minute.
    if "secondary rate limit" in response.text.lower():
        return 60 * attempt
    return None


def request(session, method, path, params=None, json=None):
    """Call a GitHub API path, waiting and retrying when rate limited."""
    url = path if path.startswith("http") else API + path
    for attempt in range(1, MAX_RETRIES + 1):
        response = session.request(method, url, params=params, json=json, timeout=30)
        if response.status_code in (403, 429):
            wait = _wait_seconds(response, attempt)
            if wait is not None:
                print(f"  rate limited, waiting {wait}s ...", flush=True)
                time.sleep(wait)
                continue
        if response.status_code >= 400:
            raise GitHubError(f"{method} {url} -> {response.status_code}: {response.text[:200]}",
                              status=response.status_code)
        # Out of quota for this window: wait now so the next call succeeds.
        if response.headers.get("X-RateLimit-Remaining") == "0":
            wait = _wait_seconds(response)
            print(f"  rate limit used up, waiting {wait}s ...", flush=True)
            time.sleep(wait)
        return response
    raise GitHubError(f"{method} {url} still rate limited after {MAX_RETRIES} tries")


def get(session, path, params=None):
    return request(session, "GET", path, params=params)


def post(session, path, json):
    return request(session, "POST", path, json=json)


def patch(session, path, json):
    return request(session, "PATCH", path, json=json)


def get_all(session, path):
    """GET every page of a list endpoint (follows the Link: next header)."""
    items = []
    url, params = path, {"per_page": 100}
    while url:
        response = get(session, url, params)
        items.extend(response.json())
        url = response.links.get("next", {}).get("url")
        params = None  # the next URL already carries the query string
    return items


def exists(session, path):
    """True if GET path succeeds; False on 404. Other errors are raised."""
    try:
        get(session, path)
    except GitHubError as e:
        if e.status == 404:
            return False
        raise
    return True


def repo_exists(session, full_name):
    return exists(session, f"/repos/{full_name}")


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
