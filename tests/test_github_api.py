from types import SimpleNamespace

from src.github_api import _wait_seconds


def fake_response(headers=None, text=""):
    return SimpleNamespace(headers=headers or {}, text=text)


def test_retry_after_header_is_honored():
    assert _wait_seconds(fake_response({"Retry-After": "7"})) == 7


def test_secondary_rate_limit_without_headers_waits_and_backs_off():
    response = fake_response(text='{"message": "You have exceeded a secondary rate limit."}')
    assert _wait_seconds(response, attempt=1) == 60
    assert _wait_seconds(response, attempt=2) == 120


def test_other_403_is_not_treated_as_rate_limit():
    assert _wait_seconds(fake_response(text='{"message": "Resource not accessible"}')) is None
