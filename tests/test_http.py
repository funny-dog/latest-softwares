from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests


def test_github_headers_include_token(monkeypatch):
    from scripts.net import github_headers

    monkeypatch.setenv("GITHUB_TOKEN", "token-123")

    headers = github_headers()

    assert headers["Authorization"] == "Bearer token-123"
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert headers["User-Agent"] == "latest-softwares-sync"


def test_browser_headers_use_browser_user_agent():
    from scripts.net import browser_headers

    headers = browser_headers()

    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert "text/html" in headers["Accept"]


def test_request_retries_transient_request_errors(monkeypatch):
    from scripts import net as http

    calls: list[str] = []

    class Response:
        status_code = 200
        text = "{}"

    def fake_request(method, url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise requests.ConnectionError("temporary reset")
        return Response()

    monkeypatch.setattr(http.requests, "request", fake_request)
    monkeypatch.setattr(http.time, "sleep", lambda _: None)

    response = http.request("GET", "https://example.test/data", retries=1)

    assert response.status_code == 200
    assert calls == ["https://example.test/data", "https://example.test/data"]


def test_request_acquires_per_host_limiter(monkeypatch):
    from scripts import net as http

    events: list[str] = []

    class Response:
        status_code = 200
        headers = {}

    class RecorderLimiter:
        def __init__(self, url: str):
            self.url = url

        def __enter__(self):
            events.append(f"enter:{self.url}")

        def __exit__(self, exc_type, exc, tb):
            events.append(f"exit:{self.url}")

    def fake_get_limiter(url):
        events.append(f"limiter:{url}")
        return RecorderLimiter(url)

    monkeypatch.setattr(http, "_get_host_limiter", fake_get_limiter)
    monkeypatch.setattr(http.requests, "request", lambda *_, **__: Response())

    response = http.get("https://example.test/data")

    assert response.status_code == 200
    assert events == [
        "limiter:https://example.test/data",
        "enter:https://example.test/data",
        "exit:https://example.test/data",
    ]


def test_host_key_normalizes_netloc():
    from scripts import net as http

    assert http._host_key("https://EXAMPLE.test:443/data?q=1") == "example.test:443"


def test_request_honors_retry_after_seconds(monkeypatch):
    from scripts import net as http

    sleeps: list[float] = []
    responses = iter(
        [
            type(
                "R",
                (),
                {
                    "status_code": 429,
                    "headers": {"Retry-After": "7"},
                    "close": lambda self: None,
                },
            )(),
            type(
                "R", (), {"status_code": 200, "headers": {}, "close": lambda self: None}
            )(),
        ]
    )

    def fake_request(method, url, **kwargs):
        return next(responses)

    monkeypatch.setattr(http.requests, "request", fake_request)
    monkeypatch.setattr(http.time, "sleep", lambda d: sleeps.append(float(d)))

    response = http.request("GET", "https://example.test/", retries=1, backoff=10)

    assert response.status_code == 200
    # 应使用 Retry-After（7s）而不是指数退避（backoff=10 → 10s）
    assert sleeps == [7.0]


def test_request_clamps_retry_after_to_max(monkeypatch):
    from scripts import net as http

    sleeps: list[float] = []
    responses = iter(
        [
            type(
                "R",
                (),
                {
                    "status_code": 503,
                    "headers": {"Retry-After": "9999"},
                    "close": lambda self: None,
                },
            )(),
            type(
                "R", (), {"status_code": 200, "headers": {}, "close": lambda self: None}
            )(),
        ]
    )
    monkeypatch.setattr(http.requests, "request", lambda *_, **__: next(responses))
    monkeypatch.setattr(http.time, "sleep", lambda d: sleeps.append(float(d)))

    http.request("GET", "https://example.test/", retries=1)

    assert sleeps == [http.MAX_RETRY_AFTER]


def test_parse_retry_after_handles_http_date():
    from scripts import net as http

    future = datetime.now(tz=timezone.utc) + timedelta(seconds=30)
    header = future.strftime("%a, %d %b %Y %H:%M:%S GMT")

    delay = http._parse_retry_after(header)

    assert delay is not None
    assert 25 <= delay <= 35  # 容许少量调度抖动


def test_parse_retry_after_returns_none_for_garbage():
    from scripts import net as http

    assert http._parse_retry_after(None) is None
    assert http._parse_retry_after("") is None
    assert http._parse_retry_after("not-a-date") is None
