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


class _JsonResponse:
    def __init__(self, status_code, body="", etag=None):
        self.status_code = status_code
        self.text = body
        self.headers = {"ETag": etag} if etag else {}
        self.closed = False

    def json(self):
        import json

        return json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def close(self):
        self.closed = True


def _reset_conditional_cache(monkeypatch, http, cache_file):
    monkeypatch.setenv(http.HTTP_CACHE_ENV, str(cache_file))
    monkeypatch.setattr(http, "_CONDITIONAL_CACHE", None)
    # atexit 注册的保存函数在测试里无意义，避免进程退出时写入临时目录
    monkeypatch.setattr(http.atexit, "register", lambda *_: None)


def test_get_json_uses_etag_and_reuses_body_on_304(tmp_path, monkeypatch):
    from scripts import net as http

    cache_file = tmp_path / "http-cache.json.gz"
    _reset_conditional_cache(monkeypatch, http, cache_file)
    url = "https://api.github.com/repos/o/r/releases/latest"
    sent_headers: list[dict] = []
    responses = iter(
        [
            _JsonResponse(200, '{"tag_name": "v1"}', etag='W/"abc"'),
            _JsonResponse(304),
        ]
    )

    def fake_request(method, req_url, headers=None, **kwargs):
        sent_headers.append(dict(headers or {}))
        return next(responses)

    monkeypatch.setattr(http.requests, "request", fake_request)

    assert http.get_json(url) == {"tag_name": "v1"}
    http._save_conditional_cache()

    # 模拟下一次 CI 运行：从磁盘重新加载缓存
    monkeypatch.setattr(http, "_CONDITIONAL_CACHE", None)
    assert http.get_json(url) == {"tag_name": "v1"}

    assert "If-None-Match" not in sent_headers[0]
    assert sent_headers[1]["If-None-Match"] == 'W/"abc"'
    assert http._CONDITIONAL_CACHE is not None
    assert http._CONDITIONAL_CACHE.hits == 1


def test_get_json_conditional_cache_only_for_github_api(tmp_path, monkeypatch):
    from scripts import net as http

    _reset_conditional_cache(monkeypatch, http, tmp_path / "cache.json.gz")
    sent_headers: list[dict] = []

    def fake_request(method, req_url, headers=None, **kwargs):
        sent_headers.append(dict(headers or {}))
        return _JsonResponse(200, "{}", etag='"x"')

    monkeypatch.setattr(http.requests, "request", fake_request)

    http.get_json("https://nodejs.org/dist/index.json")
    http.get_json("https://nodejs.org/dist/index.json")

    assert all("If-None-Match" not in h for h in sent_headers)
    assert http._CONDITIONAL_CACHE is None


def test_get_json_without_cache_env_sends_no_conditional_header(monkeypatch):
    from scripts import net as http

    monkeypatch.delenv(http.HTTP_CACHE_ENV, raising=False)
    monkeypatch.setattr(http, "_CONDITIONAL_CACHE", None)
    sent_headers: list[dict] = []

    def fake_request(method, req_url, headers=None, **kwargs):
        sent_headers.append(dict(headers or {}))
        return _JsonResponse(200, '{"ok": true}', etag='"x"')

    monkeypatch.setattr(http.requests, "request", fake_request)

    assert http.get_json("https://api.github.com/rate_limit") == {"ok": True}
    assert "If-None-Match" not in sent_headers[0]
    assert http._CONDITIONAL_CACHE is None


def test_conditional_cache_prunes_idle_entries_and_tolerates_corruption(tmp_path):
    from scripts import net as http

    cache_file = tmp_path / "cache.json.gz"
    cache_file.write_bytes(b"not gzip")
    cache = http.ConditionalCache(cache_file)  # 损坏文件不抛异常
    assert cache.lookup("https://api.github.com/a") is None

    cache.store("https://api.github.com/a", '"a"', "{}")
    cache.store("https://api.github.com/b", '"b"', "{}")
    cache._entries["https://api.github.com/b"]["used_at"] = 0
    cache.save()

    reloaded = http.ConditionalCache(cache_file)
    assert reloaded.lookup("https://api.github.com/a") is not None
    assert reloaded.lookup("https://api.github.com/b") is None


def test_set_max_connections_per_host_resets_limiters(monkeypatch):
    from scripts import net as http

    monkeypatch.setattr(http, "MAX_CONNECTIONS_PER_HOST", 4)
    monkeypatch.setattr(http, "_HOST_LIMITERS", {})

    http._get_host_limiter("https://github.com/a")
    http.set_max_connections_per_host(16)

    assert http.MAX_CONNECTIONS_PER_HOST == 16
    assert http._HOST_LIMITERS == {}
    limiter = http._get_host_limiter("https://github.com/a")
    assert limiter._initial_value == 16
