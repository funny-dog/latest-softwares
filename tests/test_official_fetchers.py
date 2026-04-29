from __future__ import annotations

from scripts.fetchers import download_page, fedora, firefox, nodejs, ubuntu


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


def test_ubuntu_fetcher_uses_latest_release_index(monkeypatch):
    responses = {
        ubuntu.RELEASES_URL: """
            <a href="25.10/">25.10/</a> Ubuntu 25.10 (Questing Quokka)
            <a href="26.04/">26.04/</a> Ubuntu 26.04 LTS (Resolute Raccoon)
        """,
        "https://releases.ubuntu.com/26.04/": """
            <a href="ubuntu-26.04-desktop-amd64.iso">desktop</a>
            <a href="ubuntu-26.04-live-server-amd64.iso">server</a>
        """,
    }

    class Response:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    monkeypatch.setattr(ubuntu, "get", lambda url, **_: Response(responses[url]))

    result = ubuntu.fetch(
        {
            "platforms": [
                {
                    "platform": "desktop-amd64",
                    "pattern": "ubuntu-{version}-desktop-amd64.iso",
                },
                {
                    "platform": "server-amd64",
                    "pattern": "ubuntu-{version}-live-server-amd64.iso",
                },
            ],
        }
    )

    assert result.version == "26.04"
    assert result.version_source == ubuntu.VERSION_SOURCE
    assert (
        result.assets[0].url
        == "https://releases.ubuntu.com/26.04/ubuntu-26.04-desktop-amd64.iso"
    )
    assert (
        result.assets[1].url
        == "https://releases.ubuntu.com/26.04/ubuntu-26.04-live-server-amd64.iso"
    )


def test_fedora_fetcher_uses_highest_release_directory(monkeypatch):
    responses = {
        fedora.RELEASES_URL: """
            <a href="43/">43/</a>
            <a href="44/">44/</a>
        """,
        "https://dl.fedoraproject.org/pub/fedora/linux/releases/44/Workstation/x86_64/iso/": """
            <a href="Fedora-Workstation-44-1.7-x86_64-CHECKSUM">checksum</a>
            <a href="Fedora-Workstation-Live-44-1.7.x86_64.iso">iso</a>
        """,
    }

    class Response:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    monkeypatch.setattr(fedora, "get", lambda url, **_: Response(responses[url]))

    result = fedora.fetch(
        {
            "platforms": [
                {
                    "platform": "workstation-live-x86_64",
                    "pattern": "Fedora-Workstation-Live-{version}-*.x86_64.iso",
                },
            ],
        }
    )

    assert result.version == "44"
    assert result.version_source == fedora.VERSION_SOURCE
    assert result.assets[0].url == (
        "https://dl.fedoraproject.org/pub/fedora/linux/releases/44/"
        "Workstation/x86_64/iso/Fedora-Workstation-Live-44-1.7.x86_64.iso"
    )


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
