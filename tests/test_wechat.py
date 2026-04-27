from __future__ import annotations

import pytest

from scripts.fetchers import wechat


@pytest.mark.parametrize(
    "version,expected",
    [
        ("3.9.10.27", True),
        ("4.0.1.15", True),
        ("3.9.11", True),
        ("214.172.387.384", False),  # 主段 >= 100
        ("1.2.3.4.5", False),  # 段数 > 4
        ("1.2", False),  # 段数 < 3
        ("3.9.99999", False),  # 段值溢出
        ("a.b.c", False),
        ("", False),
    ],
)
def test_is_plausible(version, expected):
    assert wechat._is_plausible(version) is expected


def test_homepage_parser_uses_context_anchor(monkeypatch):
    """带 WeChat 锚点的版本号优先于无锚点的 SDK 版本号。"""
    html = (
        "<html><head><meta name='sdk-version' content='214.172.387.384'></head>"
        "<body>WeChat for Windows version 3.9.11.25 released today.</body></html>"
    )

    class Resp:
        text = html

        def raise_for_status(self):
            return None

    monkeypatch.setattr(wechat, "get", lambda *_, **__: Resp())

    assert wechat._from_homepage_html() == "3.9.11.25"


def test_homepage_parser_rejects_garbage(monkeypatch):
    """没有锚点 + 全是不合理的版本号 → 返回 None，不应吞掉垃圾。"""
    html = "<html><body>code 214.172.387.384 build 999.0.0</body></html>"

    class Resp:
        text = html

        def raise_for_status(self):
            return None

    monkeypatch.setattr(wechat, "get", lambda *_, **__: Resp())

    assert wechat._from_homepage_html() is None


def test_content_disposition_extracts_version(monkeypatch):
    class Resp:
        headers = {"Content-Disposition": 'attachment; filename="WeChat-3.9.11.25.exe"'}

    monkeypatch.setattr(wechat, "head", lambda *_, **__: Resp())

    assert wechat._from_content_disposition("https://x") == "3.9.11.25"


def test_content_disposition_falls_back_when_missing(monkeypatch):
    class Resp:
        headers = {}

    monkeypatch.setattr(wechat, "head", lambda *_, **__: Resp())

    assert wechat._from_content_disposition("https://x") is None


def test_resolve_version_prefers_content_disposition(monkeypatch):
    monkeypatch.setattr(wechat, "_from_content_disposition", lambda _u: "4.0.0.1")
    monkeypatch.setattr(
        wechat, "_from_homepage_html", lambda: pytest.fail("should not be called")
    )

    assert wechat._resolve_version() == "4.0.0.1"


def test_resolve_version_falls_back_to_homepage(monkeypatch):
    monkeypatch.setattr(wechat, "_from_content_disposition", lambda _u: None)
    monkeypatch.setattr(wechat, "_from_homepage_html", lambda: "3.9.11.25")

    assert wechat._resolve_version() == "3.9.11.25"


def test_resolve_version_falls_back_to_date(monkeypatch):
    monkeypatch.setattr(wechat, "_from_content_disposition", lambda _u: None)
    monkeypatch.setattr(wechat, "_from_homepage_html", lambda: None)

    result = wechat._resolve_version()

    # 日期格式 YYYY-MM-DD
    assert len(result) == 10 and result.count("-") == 2
