from __future__ import annotations

import pytest

from scripts.fetchers import redirect_probe, updater_feed
from scripts.fetchers.base import FetchError
from scripts.link_utils import LINK_KIND_DIRECT


class _TextResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def close(self):
        self.closed = True


class _ProbeResponse:
    def __init__(self, status_code: int = 200, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.headers = headers or {}
        self.closed = False

    def close(self):
        self.closed = True


def test_electron_latest_yml_resolves_relative_path_and_release_date(monkeypatch):
    yml = """
version: 2.4.1
files:
  - url: MyApp-Setup-2.4.1.exe
    sha512: abc
    size: 98765432
path: MyApp-Setup-2.4.1.exe
releaseDate: '2026-11-20T10:00:00.000Z'
"""
    monkeypatch.setattr(updater_feed, "get", lambda *a, **kw: _TextResponse(yml))
    result = updater_feed.fetch(
        {
            "format": "electron",
            "name": "MyApp",
            "homepage": "https://example.test/",
            "platforms": [
                {
                    "platform": "win-x64",
                    "feed_url": "https://dl.example.test/win/latest.yml",
                }
            ],
        }
    )

    assert result.version == "2.4.1"
    assert result.released_at == "2026-11-20T10:00:00.000Z"
    assert result.assets[0].url == "https://dl.example.test/win/MyApp-Setup-2.4.1.exe"
    assert result.assets[0].filename == "MyApp-Setup-2.4.1.exe"
    assert result.assets[0].size == 98765432
    assert result.assets[0].link_kind == LINK_KIND_DIRECT


def test_electron_latest_mac_yml_selects_by_pattern_and_caches_feed(monkeypatch):
    mac_yml = """
version: 3.1.0
files:
  - url: App-3.1.0-arm64-mac.zip
    size: 111
  - url: App-3.1.0-arm64.dmg
    size: 222
  - url: App-3.1.0-x64.dmg
    size: 333
path: App-3.1.0-arm64-mac.zip
"""
    calls: list[str] = []

    def fake_get(url: str, **kwargs):
        calls.append(url)
        return _TextResponse(mac_yml)

    monkeypatch.setattr(updater_feed, "get", fake_get)
    result = updater_feed.fetch(
        {
            "format": "electron",
            "platforms": [
                {
                    "platform": "mac-arm64",
                    "feed_url": "https://dl.example.test/mac/latest-mac.yml",
                    "pattern": "*-arm64.dmg",
                },
                {
                    "platform": "mac-x64",
                    "feed_url": "https://dl.example.test/mac/latest-mac.yml",
                    "pattern": "*-x64.dmg",
                },
            ],
        }
    )

    assert len(calls) == 1
    assert result.version == "3.1.0"
    assert result.assets[0].url == "https://dl.example.test/mac/App-3.1.0-arm64.dmg"
    assert result.assets[0].size == 222
    assert result.assets[1].url == "https://dl.example.test/mac/App-3.1.0-x64.dmg"
    assert result.assets[1].size == 333


def test_electron_errors_on_ambiguous_or_missing_version(monkeypatch):
    mac_yml = """
version: 1.0.0
files:
  - url: a-arm64.dmg
  - url: b-arm64.dmg
"""
    monkeypatch.setattr(updater_feed, "get", lambda *a, **kw: _TextResponse(mac_yml))
    with pytest.raises(FetchError, match="multiple files"):
        updater_feed.fetch(
            {
                "format": "electron",
                "platforms": [
                    {
                        "platform": "mac-arm64",
                        "feed_url": "https://dl.example.test/latest-mac.yml",
                        "pattern": "*-arm64.dmg",
                    }
                ],
            }
        )

    monkeypatch.setattr(
        updater_feed, "get", lambda *a, **kw: _TextResponse("path: app.exe\n")
    )
    with pytest.raises(FetchError, match="missing version"):
        updater_feed.fetch(
            {
                "format": "electron",
                "platforms": [
                    {
                        "platform": "win-x64",
                        "feed_url": "https://dl.example.test/latest.yml",
                    }
                ],
            }
        )


def test_sparkle_appcast_handles_attr_and_element_versions_and_picks_highest(
    monkeypatch,
):
    xml = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
  <channel>
    <item>
      <title>Version 1.9.0</title>
      <pubDate>Mon, 01 Nov 2026 12:00:00 +0000</pubDate>
      <enclosure url="https://dl.example.test/App-1.9.0.dmg"
                 sparkle:shortVersionString="1.9.0"
                 sparkle:version="190"
                 length="1000" />
    </item>
    <item>
      <title>Version 1.10.0</title>
      <pubDate>Tue, 24 Nov 2026 08:30:00 +0000</pubDate>
      <sparkle:shortVersionString>1.10.0</sparkle:shortVersionString>
      <sparkle:version>1100</sparkle:version>
      <enclosure url="releases/App-1.10.0.dmg" length="2048" sparkle:os="macos" />
    </item>
  </channel>
</rss>
"""
    monkeypatch.setattr(updater_feed, "get", lambda *a, **kw: _TextResponse(xml))
    result = updater_feed.fetch(
        {
            "format": "sparkle",
            "platforms": [
                {
                    "platform": "mac-universal",
                    "feed_url": "https://dl.example.test/appcast.xml",
                    "os": "macos",
                }
            ],
        }
    )

    assert result.version == "1.10.0"
    assert result.released_at == "2026-11-24T08:30:00+00:00"
    assert result.assets[0].url == "https://dl.example.test/releases/App-1.10.0.dmg"
    assert result.assets[0].filename == "App-1.10.0.dmg"
    assert result.assets[0].size == 2048


def test_sparkle_rejects_ambiguous_enclosures_and_bad_xml(monkeypatch):
    xml = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
  <channel>
    <item>
      <enclosure url="https://dl.example.test/App-arm64.dmg" sparkle:shortVersionString="2.0.0" />
    </item>
    <item>
      <enclosure url="https://dl.example.test/App-x64.dmg" sparkle:shortVersionString="2.0.0" />
    </item>
  </channel>
</rss>
"""
    monkeypatch.setattr(updater_feed, "get", lambda *a, **kw: _TextResponse(xml))
    with pytest.raises(FetchError, match="multiple enclosures"):
        updater_feed.fetch(
            {
                "format": "sparkle",
                "platforms": [
                    {
                        "platform": "mac-arm64",
                        "feed_url": "https://dl.example.test/appcast.xml",
                    }
                ],
            }
        )

    monkeypatch.setattr(updater_feed, "get", lambda *a, **kw: _TextResponse("<rss>"))
    with pytest.raises(FetchError, match="invalid Sparkle XML"):
        updater_feed.fetch(
            {
                "format": "sparkle",
                "platforms": [
                    {
                        "platform": "mac-arm64",
                        "feed_url": "https://dl.example.test/appcast.xml",
                    }
                ],
            }
        )


def test_redirect_probe_follows_302_chain_and_extracts_version(monkeypatch):
    responses = {
        "https://example.test/download/latest": _ProbeResponse(
            302, {"Location": "https://cdn.example.test/rel/AppSetup-6.0.9.5.exe"}
        ),
        "https://cdn.example.test/rel/AppSetup-6.0.9.5.exe": _ProbeResponse(
            200, {"Content-Length": "424242"}
        ),
    }

    monkeypatch.setattr(redirect_probe, "head", lambda url, **kw: responses[url])

    kept = redirect_probe.fetch(
        {
            "name": "Example",
            "version_regex": r"AppSetup-(\d+\.\d+\.\d+\.\d+)\.exe",
            "platforms": [
                {
                    "platform": "win-x64",
                    "url": "https://example.test/download/latest",
                }
            ],
        }
    )
    assert kept.version == "6.0.9.5"
    assert kept.assets[0].url == "https://example.test/download/latest"
    assert kept.assets[0].filename == "AppSetup-6.0.9.5.exe"
    assert kept.assets[0].size == 424242
    assert all(r.closed for r in responses.values())

    for r in responses.values():
        r.closed = False
    final_mode = redirect_probe.fetch(
        {
            "use_final_url": True,
            "platforms": [
                {
                    "platform": "win-x64",
                    "url": "https://example.test/download/latest",
                }
            ],
        }
    )
    assert (
        final_mode.assets[0].url == "https://cdn.example.test/rel/AppSetup-6.0.9.5.exe"
    )


def test_redirect_probe_falls_back_from_405_head_to_get_and_prefers_rfc6266(
    monkeypatch,
):
    monkeypatch.setattr(redirect_probe, "head", lambda *a, **kw: _ProbeResponse(405))
    monkeypatch.setattr(
        redirect_probe,
        "get",
        lambda *a, **kw: _ProbeResponse(
            200,
            {
                "Content-Disposition": (
                    'attachment; filename="App-1.0.exe"; '
                    "filename*=UTF-8''App-3.9.12.50-x64.exe"
                ),
                "Content-Length": "1000",
            },
        ),
    )

    result = redirect_probe.fetch(
        {
            "platforms": [
                {
                    "platform": "win-x64",
                    "url": "https://example.test/latest",
                    "version_regex": r"App-(\d+\.\d+\.\d+\.\d+)-x64\.exe",
                }
            ]
        }
    )
    assert result.version == "3.9.12.50"
    assert result.assets[0].filename == "App-3.9.12.50-x64.exe"


def test_redirect_probe_enforces_hop_limit_public_url_and_missing_version(monkeypatch):
    monkeypatch.setattr(
        redirect_probe,
        "head",
        lambda url, **kw: _ProbeResponse(
            302, {"Location": "https://example.test/loop"}
        ),
    )
    with pytest.raises(FetchError, match="exceeded max_hops"):
        redirect_probe.probe_redirect("https://example.test/loop", max_hops=2)

    monkeypatch.setattr(
        redirect_probe,
        "head",
        lambda url, **kw: _ProbeResponse(
            302, {"Location": "http://127.0.0.1/evil.exe"}
        ),
    )
    with pytest.raises(FetchError, match="non-public URL"):
        redirect_probe.probe_redirect("https://example.test/start")

    monkeypatch.setattr(
        redirect_probe,
        "head",
        lambda url, **kw: _ProbeResponse(200, {}),
    )
    with pytest.raises(FetchError, match="could not extract version"):
        redirect_probe.fetch(
            {
                "version_regex": r"v(\d+\.\d+)",
                "platforms": [
                    {"platform": "win-x64", "url": "https://example.test/setup.exe"}
                ],
            }
        )


def test_json_feed_extracts_version_url_sha256_and_custom_keys(monkeypatch):
    payload = (
        '{"url":"https://dl.example.test/DevinUserSetup-x64-3.15.14.exe",'
        '"productVersion":"1.141.2","windsurfVersion":"3.15.14",'
        '"timestamp":1795637803000,"sha256hash":"' + ("a" * 64) + '"}'
    )
    monkeypatch.setattr(updater_feed, "get", lambda *a, **kw: _TextResponse(payload))
    res = updater_feed.fetch(
        {
            "format": "json",
            "version_key": "windsurfVersion",
            "platforms": [
                {
                    "platform": "win-x64",
                    "feed_url": "https://api.example.test/update/win32-x64/stable/latest",
                }
            ],
        }
    )
    assert res.version == "3.15.14"
    assert res.released_at == "2026-11-25T20:16:43+00:00"
    assert res.assets[0].url == "https://dl.example.test/DevinUserSetup-x64-3.15.14.exe"
    assert res.assets[0].sha256 == "a" * 64
    assert res.assets[0].filename == "DevinUserSetup-x64-3.15.14.exe"

    cursor_payload = '{"downloadUrl":"https://dl.example.test/Cursor-3.32.4.AppImage","version":"3.32.4"}'
    monkeypatch.setattr(
        updater_feed, "get", lambda *a, **kw: _TextResponse(cursor_payload)
    )
    cursor_res = updater_feed.fetch(
        {
            "format": "json",
            "platforms": [
                {
                    "platform": "linux-x64",
                    "feed_url": "https://api2.example.test/download/stable/linux-x64",
                }
            ],
        }
    )
    assert cursor_res.version == "3.32.4"
    assert cursor_res.assets[0].url == "https://dl.example.test/Cursor-3.32.4.AppImage"
