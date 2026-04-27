from __future__ import annotations

import requests


def test_github_headers_include_token(monkeypatch):
    from scripts.http import github_headers

    monkeypatch.setenv("GITHUB_TOKEN", "token-123")

    headers = github_headers()

    assert headers["Authorization"] == "Bearer token-123"
    assert headers["Accept"] == "application/vnd.github+json"
    assert headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert headers["User-Agent"] == "latest-softwares-sync"


def test_browser_headers_use_browser_user_agent():
    from scripts.http import browser_headers

    headers = browser_headers()

    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert "text/html" in headers["Accept"]


def test_request_retries_transient_request_errors(monkeypatch):
    from scripts import http

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
