from __future__ import annotations

from scripts.discover.sources import github


def test_discover_builds_candidates_with_assets(monkeypatch):
    def fake_get_json(url, **kwargs):
        if "search/repositories" in url:
            return {
                "items": [
                    {
                        "full_name": "pbatard/rufus",
                        "name": "rufus",
                        "stargazers_count": 29000,
                        "description": "USB tool",
                        "topics": ["usb", "windows"],
                    }
                ]
            }
        # latest release
        return {
            "published_at": "2026-01-01T00:00:00Z",
            "assets": [
                {"name": "rufus-4.5.exe"},
                {"name": "rufus-4.5p.exe"},
            ],
        }

    monkeypatch.setattr(github, "get_json", fake_get_json)
    cands = github.discover(min_stars=5000, max_scan=10)
    assert len(cands) == 1
    c = cands[0]
    assert c.repo == "pbatard/rufus"
    assert c.stars == 29000
    assert c.asset_names == ["rufus-4.5.exe", "rufus-4.5p.exe"]
    assert c.topics == ["usb", "windows"]


def test_discover_skips_repo_without_release(monkeypatch):
    def fake_get_json(url, **kwargs):
        if "search/repositories" in url:
            return {
                "items": [
                    {
                        "full_name": "a/b",
                        "name": "b",
                        "stargazers_count": 9000,
                        "description": "",
                        "topics": [],
                    }
                ]
            }
        raise RuntimeError("404 no release")

    monkeypatch.setattr(github, "get_json", fake_get_json)
    cands = github.discover(min_stars=5000, max_scan=10)
    assert cands == []
