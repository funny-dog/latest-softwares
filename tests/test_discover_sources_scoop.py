from __future__ import annotations

from scripts.discover.sources import scoop
from scripts.discover.state import DiscoveryState


def test_scoop_extract_download_url_prefers_64bit():
    data = {
        "url": "https://example.com/32bit.zip",
        "architecture": {
            "64bit": {
                "url": "https://example.com/64bit.zip",
            }
        },
    }
    url = scoop.extract_scoop_download_url(data)
    assert url == "https://example.com/64bit.zip"


def test_scoop_discover_parses_bucket_offline(monkeypatch):
    bucket_files = [
        {
            "name": "my-tool.json",
            "download_url": "https://raw.githubusercontent.com/ScoopInstaller/Main/master/bucket/my-tool.json",
        }
    ]
    manifest = {
        "version": "1.0",
        "description": "A scoop tool",
        "homepage": "https://github.com/scoopuser/my-tool",
        "url": "https://github.com/scoopuser/my-tool/releases/download/v1.0/tool.zip",
    }

    def fake_get_json(url, **kwargs):
        if "git/trees" in url:
            return {
                "tree": [
                    {"type": "blob", "path": "bucket/" + f["name"]}
                    for f in bucket_files
                ]
            }
        if "my-tool.json" in url:
            return manifest
        return []

    monkeypatch.setattr(scoop, "get_json", fake_get_json)

    state = DiscoveryState()
    cands = scoop.discover(max_scan=5, state=state)

    assert len(cands) == 1
    c = cands[0]
    assert c.name == "my-tool"
    assert c.external_id == "scoop:main/my-tool"
    assert c.repo == "scoopuser/my-tool"
    assert c.platform == "win"
    assert (
        c.download_url
        == "https://github.com/scoopuser/my-tool/releases/download/v1.0/tool.zip"
    )


def test_scoop_network_failure_isolated(monkeypatch):
    def fake_get_json(url, **kwargs):
        raise RuntimeError("scoop github api rate limit")

    monkeypatch.setattr(scoop, "get_json", fake_get_json)
    state = DiscoveryState()
    cands = scoop.discover(max_scan=5, state=state)
    assert cands == []
    assert scoop.LAST_ERROR == "scoop github api rate limit"
