from __future__ import annotations

import pytest

from scripts.fetchers import everything
from scripts.fetchers.base import FetchError


class _FakeResp:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


def test_resolves_url_template_with_parsed_version(monkeypatch):
    monkeypatch.setattr(
        everything,
        "get",
        lambda *_, **__: _FakeResp("Download Everything 1.4.1.1033 today"),
    )
    args = {
        "platforms": [
            {
                "platform": "win-x64",
                "download_url": "https://x/Everything-{version}.x64-Setup.exe",
            },
            {
                "platform": "win-x86",
                "download_url": "https://x/Everything-{version}.x86-Setup.exe",
            },
        ]
    }

    result = everything.fetch(args)

    assert result.version == "1.4.1.1033"
    urls = {a.platform: a.url for a in result.assets}
    assert urls["win-x64"] == "https://x/Everything-1.4.1.1033.x64-Setup.exe"
    assert urls["win-x86"] == "https://x/Everything-1.4.1.1033.x86-Setup.exe"


def test_url_without_placeholder_is_passed_through(monkeypatch):
    """没有 {version} 占位符的旧式 URL 应原样保留，向后兼容。"""
    monkeypatch.setattr(
        everything, "get", lambda *_, **__: _FakeResp("Download Everything 1.4.1.1033")
    )
    args = {
        "platforms": [
            {"platform": "win-x64", "download_url": "https://x/static-link.exe"},
        ]
    }

    result = everything.fetch(args)

    assert result.assets[0].url == "https://x/static-link.exe"


def test_fetch_error_when_version_unparseable(monkeypatch):
    """版本号解析不到时应抛 FetchError，而不是写出含 'unknown' 的坏 URL。"""
    monkeypatch.setattr(
        everything, "get", lambda *_, **__: _FakeResp("<html>没有版本号</html>")
    )
    args = {
        "platforms": [
            {"platform": "win-x64", "download_url": "https://x/{version}.exe"}
        ]
    }

    with pytest.raises(FetchError, match="无法从下载页解析版本号"):
        everything.fetch(args)


def test_fetch_error_when_no_platforms():
    with pytest.raises(FetchError, match="platforms 不能为空"):
        everything.fetch({})
