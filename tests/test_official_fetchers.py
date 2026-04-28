from __future__ import annotations

from scripts.fetchers import download_page, firefox, nodejs


def test_firefox_fetcher_uses_mozilla_product_details(monkeypatch):
    monkeypatch.setattr(
        firefox,
        "get_json",
        lambda *_, **__: {"LATEST_FIREFOX_VERSION": "145.0.1"},
    )

    result = firefox.fetch(
        {
            "lang": "en-US",
            "platforms": [
                {"platform": "win-x64", "os": "win64"},
                {"platform": "mac-universal", "os": "osx"},
            ],
        }
    )

    assert result.version == "145.0.1"
    assert result.version_source == firefox.VERSION_SOURCE
    assert [asset.platform for asset in result.assets] == ["win-x64", "mac-universal"]
    assert "product=firefox-latest-ssl" in result.assets[0].url
    assert "lang=en-US" in result.assets[0].url


def test_nodejs_fetcher_uses_latest_lts_release(monkeypatch):
    monkeypatch.setattr(
        nodejs,
        "get_json",
        lambda *_, **__: [
            {"version": "v26.0.0", "lts": False, "files": ["win-x64"]},
            {
                "version": "v24.11.1",
                "lts": "Krypton",
                "files": ["win-x64-zip", "linux-x64"],
            },
        ],
    )

    result = nodejs.fetch(
        {
            "platforms": [
                {
                    "platform": "win-x64",
                    "file_key": "win-x64-zip",
                    "filename": "node-{version}-win-x64.zip",
                },
                {
                    "platform": "linux-x64",
                    "file_key": "linux-x64",
                    "filename": "node-{version}-linux-x64.tar.xz",
                },
            ],
        }
    )

    assert result.version == "24.11.1"
    assert result.version_source == nodejs.VERSION_SOURCE
    assert result.assets[0].url.endswith("/v24.11.1/node-v24.11.1-win-x64.zip")
    assert result.assets[1].url.endswith("/v24.11.1/node-v24.11.1-linux-x64.tar.xz")


def test_download_page_fetcher_marks_sync_date_and_preserves_link_kind():
    result = download_page.fetch(
        {
            "source": "Official test download page",
            "homepage": "https://example.test/app",
            "platforms": [
                {
                    "platform": "win-x64",
                    "download_url": "https://example.test/latest.exe",
                    "link_kind": "direct",
                }
            ],
        }
    )

    assert result.source == "Official test download page"
    assert result.version_kind == "sync_date"
    assert result.version_source == "UTC sync date; no public version API"
    assert result.assets[0].link_kind == "direct"
