from __future__ import annotations

import pytest

from scripts.fetchers import linux_store
from scripts.fetchers.base import FetchError
from scripts.link_utils import LINK_KIND_DIRECT, LINK_KIND_LANDING_PAGE


def test_flathub_extracts_stable_release_and_flatpakref(monkeypatch):
    def fake_get_json(url: str, **kwargs):
        assert url == "https://flathub.org/api/v2/appstream/com.discordapp.Discord"
        return {
            "id": "com.discordapp.Discord",
            "name": "Discord",
            "is_eol": False,
            "urls": {"homepage": "https://discord.com"},
            "releases": [
                {
                    "version": "1.0.172-beta",
                    "type": "development",
                    "timestamp": "1795400000",
                },
                {
                    "version": "1.0.171",
                    "type": "stable",
                    "timestamp": "1795392000",
                    "url": "https://discord.com/changelog",
                },
            ],
        }

    monkeypatch.setattr(linux_store, "get_json", fake_get_json)
    result = linux_store.fetch(
        {
            "provider": "flathub",
            "package": "com.discordapp.Discord",
            "platforms": [{"platform": "linux-x64"}],
        }
    )

    assert result.version == "1.0.171"
    assert result.homepage == "https://discord.com"
    assert result.notes_url == "https://discord.com/changelog"
    assert result.released_at == "2026-11-23T00:00:00+00:00"
    assert len(result.assets) == 1
    asset = result.assets[0]
    assert asset.platform == "linux-x64"
    assert (
        asset.url
        == "https://dl.flathub.org/repo/appstream/com.discordapp.Discord.flatpakref"
    )
    assert asset.link_kind == LINK_KIND_DIRECT
    assert asset.filename == "com.discordapp.Discord.flatpakref"


def test_flathub_landing_page_mode(monkeypatch):
    monkeypatch.setattr(
        linux_store,
        "get_json",
        lambda *a, **kw: {
            "id": "org.videolan.VLC",
            "releases": [{"version": "3.0.24", "date": "2026-09-01"}],
        },
    )
    result = linux_store.fetch(
        {
            "provider": "flathub",
            "package": "org.videolan.VLC",
            "link_kind": "landing_page",
            "platforms": [{"platform": "linux-x64"}],
        }
    )
    assert result.version == "3.0.24"
    assert result.released_at == "2026-09-01"
    assert result.assets[0].url == "https://flathub.org/en/apps/org.videolan.VLC"
    assert result.assets[0].link_kind == LINK_KIND_LANDING_PAGE
    assert result.assets[0].filename is None


@pytest.mark.parametrize(
    ("package", "platform", "payload", "match"),
    [
        ("bad", "linux-x64", {}, "invalid Flathub app id"),
        ("../bad.app", "linux-x64", {}, "invalid Flathub app id"),
        ("org.kde.krita", "win-x64", {}, "unsupported Flathub platform"),
        (
            "org.kde.krita",
            "linux-x64",
            {"id": "org.other.App", "releases": [{"version": "1.0"}]},
            "identity mismatch",
        ),
        (
            "org.kde.krita",
            "linux-x64",
            {"id": "org.kde.krita", "is_eol": True, "releases": [{"version": "1.0"}]},
            "end-of-life",
        ),
        (
            "org.kde.krita",
            "linux-x64",
            {"id": "org.kde.krita", "releases": []},
            "no release version",
        ),
    ],
)
def test_flathub_validation_and_errors(monkeypatch, package, platform, payload, match):
    monkeypatch.setattr(linux_store, "get_json", lambda *a, **kw: payload)
    with pytest.raises(FetchError, match=match):
        linux_store.fetch(
            {
                "provider": "flathub",
                "package": package,
                "platforms": [{"platform": platform}],
            }
        )


def test_snapcraft_selects_stable_default_track_and_sends_series_header(monkeypatch):
    def fake_get_json(url: str, **kwargs):
        assert url == "https://api.snapcraft.io/v2/snaps/info/slack"
        assert kwargs.get("headers") == {"Snap-Device-Series": "16"}
        return {
            "name": "slack",
            "default-track": "latest",
            "snap": {"title": "Slack", "website": "https://slack.com/"},
            "channel-map": [
                {
                    "channel": {
                        "architecture": "amd64",
                        "risk": "edge",
                        "track": "latest",
                    },
                    "version": "4.99.0-edge",
                },
                {
                    "channel": {
                        "architecture": "amd64",
                        "risk": "stable",
                        "track": "latest",
                        "released-at": "2026-11-19T19:49:44+00:00",
                    },
                    "version": "4.53.292",
                    "download": {
                        "url": "https://api.snapcraft.io/api/v1/snaps/download/abc_271.snap",
                        "size": 233066496,
                    },
                },
                {
                    "channel": {
                        "architecture": "arm64",
                        "risk": "stable",
                        "track": "latest",
                    },
                    "version": "4.53.290",
                    "download": {
                        "url": "https://api.snapcraft.io/api/v1/snaps/download/abc_270.snap",
                        "size": 220000000,
                    },
                },
            ],
        }

    monkeypatch.setattr(linux_store, "get_json", fake_get_json)
    result = linux_store.fetch(
        {
            "provider": "snapcraft",
            "package": "slack",
            "platforms": [{"platform": "linux-x64"}, {"platform": "linux-arm64"}],
        }
    )

    assert result.version == "4.53.292"
    assert result.homepage == "https://slack.com/"
    assert result.released_at == "2026-11-19T19:49:44+00:00"
    assert result.assets[0].url == "https://snapcraft.io/slack"
    assert result.assets[0].link_kind == LINK_KIND_LANDING_PAGE
    assert result.assets[0].version == "4.53.292"
    assert result.assets[1].version == "4.53.290"


def test_snapcraft_direct_mode_extracts_download_url_and_size(monkeypatch):
    monkeypatch.setattr(
        linux_store,
        "get_json",
        lambda *a, **kw: {
            "name": "vlc",
            "default-track": "latest",
            "channel-map": [
                {
                    "channel": {
                        "architecture": "amd64",
                        "risk": "stable",
                        "track": "latest",
                    },
                    "version": "3.0.24",
                    "download": {
                        "url": "https://api.snapcraft.io/api/v1/snaps/download/vlc_1.snap",
                        "size": 123456,
                    },
                }
            ],
        },
    )
    result = linux_store.fetch(
        {
            "provider": "snapcraft",
            "package": "vlc",
            "link_kind": "direct",
            "platforms": [{"platform": "linux-x64"}],
        }
    )
    assert (
        result.assets[0].url
        == "https://api.snapcraft.io/api/v1/snaps/download/vlc_1.snap"
    )
    assert result.assets[0].link_kind == LINK_KIND_DIRECT
    assert result.assets[0].size == 123456


@pytest.mark.parametrize(
    ("package", "platform", "payload", "match"),
    [
        ("Bad_Name", "linux-x64", {}, "invalid Snapcraft"),
        ("slack", "mac-arm64", {}, "unsupported Snapcraft platform"),
        (
            "slack",
            "linux-x64",
            {"name": "other", "channel-map": [{"channel": {}, "version": "1"}]},
            "identity mismatch",
        ),
        (
            "slack",
            "linux-arm64",
            {
                "name": "slack",
                "default-track": "latest",
                "channel-map": [
                    {
                        "channel": {
                            "architecture": "amd64",
                            "risk": "stable",
                            "track": "latest",
                        },
                        "version": "1.0",
                    }
                ],
            },
            "no latest/stable release for arm64",
        ),
    ],
)
def test_snapcraft_errors(monkeypatch, package, platform, payload, match):
    monkeypatch.setattr(linux_store, "get_json", lambda *a, **kw: payload)
    with pytest.raises(FetchError, match=match):
        linux_store.fetch(
            {
                "provider": "snapcraft",
                "package": package,
                "platforms": [{"platform": platform}],
            }
        )


def test_linux_store_multi_source_and_package_manifest_tuple(monkeypatch):
    def fake_get_json(url: str, **kwargs):
        if "flathub.org" in url:
            return {
                "id": "org.kde.krita",
                "releases": [{"version": "5.3.4"}],
                "urls": {"homepage": "https://krita.org/"},
            }
        return {
            "name": "krita",
            "default-track": "latest",
            "channel-map": [
                {
                    "channel": {
                        "architecture": "amd64",
                        "risk": "stable",
                        "track": "latest",
                    },
                    "version": "5.3.4",
                },
                {
                    "channel": {
                        "architecture": "arm64",
                        "risk": "stable",
                        "track": "latest",
                    },
                    "version": "5.3.3",
                },
            ],
        }

    monkeypatch.setattr(linux_store, "get_json", fake_get_json)

    ver, src, ver_src, hp, assets = linux_store.fetch_linux_source(
        {
            "provider": "flathub",
            "package": "org.kde.krita",
            "platforms": [{"platform": "linux-x64"}],
        },
        include_asset_version=True,
    )
    assert ver == "5.3.4"
    assert "flathub" in src
    assert "Flathub" in ver_src
    assert hp == "https://krita.org/"
    assert assets[0].version == "5.3.4"

    multi = linux_store.fetch(
        {
            "sources": [
                {
                    "provider": "flathub",
                    "package": "org.kde.krita",
                    "platforms": [{"platform": "linux-x64"}],
                },
                {
                    "provider": "snapcraft",
                    "package": "krita",
                    "platforms": [{"platform": "linux-arm64"}],
                },
            ]
        }
    )
    assert [a.platform for a in multi.assets] == ["linux-x64", "linux-arm64"]
    assert multi.assets[0].version == "5.3.4"
    assert multi.assets[1].version == "5.3.3"

    with pytest.raises(FetchError, match="duplicate platform"):
        linux_store.fetch(
            {
                "sources": [
                    {
                        "provider": "flathub",
                        "package": "org.kde.krita",
                        "platforms": [{"platform": "linux-x64"}],
                    },
                    {
                        "provider": "snapcraft",
                        "package": "krita",
                        "platforms": [{"platform": "linux-x64"}],
                    },
                ]
            }
        )
