from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app_core.downloads import asset_available, url_expiry
from scripts import link_verifier

NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)
CONFIG = {
    "id": "example",
    "name": "Example App",
    "homepage": "https://example.test/download",
}


class Response:
    def __init__(self, body=b"MZinstaller", status=200, headers=None):
        self.body = body
        self.status_code = status
        self.headers = headers or {"Content-Type": "application/octet-stream"}
        self.raw = self
        self.closed = False
        self.read_sizes = []

    def read(self, size, decode_content=True):
        self.read_sizes.append(size)
        return self.body[:size]

    def close(self):
        self.closed = True


def verify(monkeypatch, response, **asset):
    monkeypatch.setattr(link_verifier, "get", lambda *a, **kw: response)
    return link_verifier.verify_link(
        {"platform": "win-x64", "url": "https://example.test/app-x64.exe", **asset},
        CONFIG,
        now=NOW,
    )


def test_direct_link_checks_bounded_content_and_closes_response(monkeypatch):
    response = Response()
    result = verify(monkeypatch, response)
    assert result["status"] == "verified"
    assert response.read_sizes == [65536]
    assert response.closed


def test_http_200_html_is_not_an_installer(monkeypatch):
    result = verify(
        monkeypatch,
        Response(b"<html>not found</html>", headers={"Content-Type": "text/html"}),
    )
    assert result["status"] == "failed"


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_exhausted_server_errors_are_transient(monkeypatch, status):
    response = Response(status=status)
    result = verify(monkeypatch, response)
    assert result["status"] == "transient"
    assert result["reason"] == f"HTTP {status}"
    assert response.closed


@pytest.mark.parametrize(
    "prefix_size,expected", [(85000, "verified"), (600000, "unverified")]
)
def test_landing_page_has_a_separate_bounded_sample(monkeypatch, prefix_size, expected):
    body = (
        b"<html><script>" + b"x" * prefix_size + b"</script>Example App download</html>"
    )
    response = Response(body, headers={"Content-Type": "text/html"})
    result = verify(
        monkeypatch,
        response,
        url="https://example.test/download",
        link_kind="landing_page",
    )
    assert result["status"] == expected
    assert response.read_sizes == [link_verifier.HTML_SAMPLE_BYTES]
    assert response.closed


@pytest.mark.parametrize(
    "body,expected",
    [
        (
            b"<html><script>Example App download</script>Unrelated page</html>",
            "unverified",
        ),
        (
            b"<html><script>temporarily unavailable</script>Example App download</html>",
            "verified",
        ),
    ],
)
def test_script_strings_are_not_page_evidence(monkeypatch, body, expected):
    result = verify(
        monkeypatch,
        Response(body, headers={"Content-Type": "text/html"}),
        url="https://example.test/download",
        link_kind="landing_page",
    )
    assert result["status"] == expected


def test_architecture_mismatch_and_wrong_file_header_are_rejected(monkeypatch):
    assert (
        verify(monkeypatch, Response(), url="https://example.test/app-arm64.exe")[
            "status"
        ]
        == "failed"
    )
    assert verify(monkeypatch, Response(b"not an exe"))["status"] == "failed"


@pytest.mark.parametrize(
    "body,status",
    [
        (b"<html>Example App download</html>", "verified"),
        (b"<html>Other software download</html>", "unverified"),
        (b"<html>Example App news</html>", "unverified"),
    ],
)
def test_landing_page_requires_software_identity_and_download_entry(
    monkeypatch, body, status
):
    result = verify(
        monkeypatch,
        Response(body, headers={"Content-Type": "text/html"}),
        url=CONFIG["homepage"],
        link_kind="landing_page",
    )
    assert result["status"] == status


def test_unknown_redirect_host_is_never_requested(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return Response(
            status=302, headers={"Location": "https://unknown.test/wrong.exe"}
        )

    monkeypatch.setattr(link_verifier, "get", get)
    result = link_verifier.verify_link(
        {"platform": "win-x64", "url": "https://example.test/app.exe"}, CONFIG, now=NOW
    )
    assert result["status"] == "unverified"
    assert calls == ["https://example.test/app.exe"]


def test_restricted_access_is_distinct_from_dead_link(monkeypatch):
    assert verify(monkeypatch, Response(status=403))["status"] == "restricted"
    assert verify(monkeypatch, Response(status=404))["status"] == "failed"


MAINTENANCE_HTML = (
    b"<html><body>Our website is temporarily down for maintenance. "
    b"We expect to be back up shortly.</body></html>"
)


@pytest.mark.parametrize(
    "url,link_kind",
    [
        ("https://example.test/download", "landing_page"),
        ("https://example.test/app-x64.exe", "direct"),
    ],
)
def test_maintenance_page_is_transient_not_dead_link(monkeypatch, url, link_kind):
    """上游整站维护页既不是死链也不是反爬，必须与 404/403 区分开。"""
    result = verify(
        monkeypatch,
        Response(MAINTENANCE_HTML, headers={"Content-Type": "text/html"}),
        url=url,
        link_kind=link_kind,
    )
    assert result["status"] == "transient"
    assert result["reason"] == "upstream maintenance page"


def test_ordinary_error_page_is_still_failed(monkeypatch):
    """普通错误页不能被维护页识别误放行。"""
    result = verify(
        monkeypatch,
        Response(b"<html>Not found</html>", headers={"Content-Type": "text/html"}),
        url=CONFIG["homepage"],
        link_kind="landing_page",
    )
    assert result["status"] == "unverified"


def test_expired_signatures_are_rejected_without_request(monkeypatch):
    monkeypatch.setattr(
        link_verifier,
        "get",
        lambda *a, **kw: pytest.fail("must not request expired URL"),
    )
    url = "https://example.test/app.exe?X-Amz-Date=20261020T000000Z&X-Amz-Expires=3600"
    assert url_expiry(url) == datetime(2026, 10, 20, 1, tzinfo=timezone.utc)
    assert (
        link_verifier.verify_link({"platform": "win-x64", "url": url}, CONFIG, now=NOW)[
            "status"
        ]
        == "failed"
    )


def test_runtime_honors_verification_and_expiry():
    asset = {
        "url": "https://example.test/app.exe",
        "verification": {
            "status": "verified",
            "valid_until": (NOW + timedelta(hours=1)).isoformat(),
        },
    }
    assert asset_available(asset, NOW)
    assert not asset_available(asset, NOW + timedelta(hours=2))
    assert not asset_available({**asset, "verification": {"status": "restricted"}}, NOW)
    assert not asset_available({"url": "javascript:alert(1)"}, NOW)


@pytest.mark.parametrize("kind,has_range", [("direct", True), ("landing_page", False)])
def test_range_header_only_used_for_binary_downloads(monkeypatch, kind, has_range):
    calls = []
    response = Response(
        b"<html>Example App download</html>", headers={"Content-Type": "text/html"}
    )

    def get(url, **kwargs):
        calls.append(kwargs["headers"])
        return response

    monkeypatch.setattr(link_verifier, "get", get)
    link_verifier.verify_link(
        {"url": CONFIG["homepage"], "platform": "win-x64", "link_kind": kind},
        CONFIG,
        now=NOW,
    )
    assert ("Range" in calls[0]) is has_range
    assert response.read_sizes == [
        65536 if has_range else link_verifier.HTML_SAMPLE_BYTES
    ]
    assert response.closed
