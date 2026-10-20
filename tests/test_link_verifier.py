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
