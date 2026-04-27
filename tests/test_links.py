from __future__ import annotations

from scripts import link_utils, validate_links
from scripts.fetchers.base import AssetInfo, FetchResult


def test_direct_link_detection_uses_shared_extensions():
    assert link_utils.is_direct_link("https://example.test/app.exe?token=1")
    assert link_utils.is_direct_link("https://example.test/app.tar.gz")
    assert not link_utils.is_direct_link("https://example.test/download/")


def test_refetch_repair_uses_registered_fetcher(monkeypatch):
    calls: list[dict] = []

    def fake_fetcher(args):
        calls.append(args)
        return FetchResult(
            id="",
            name="Example",
            version="2.0",
            source="test",
            assets=[
                AssetInfo(platform="win-x64", url="https://example.test/new.exe"),
                AssetInfo(platform="mac-arm64", url="https://example.test/new.dmg"),
            ],
        )

    monkeypatch.setitem(validate_links.FETCHERS, "github_release", fake_fetcher)

    fixed_url = validate_links._fix_by_refetch(
        {
            "id": "example",
            "fetcher": "github_release",
            "args": {"repo": "owner/repo", "assets": []},
        },
        {"platform": "mac-arm64", "url": "https://example.test/old.dmg"},
    )

    assert fixed_url == "https://example.test/new.dmg"
    assert calls == [{"repo": "owner/repo", "assets": []}]
