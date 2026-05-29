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


def test_discover_search_failure_degrades_without_raising(monkeypatch):
    """search 调用失败（限流/网络）应返回已收集候选，绝不抛异常崩整轮。"""

    def fake_get_json(url, **kwargs):
        raise RuntimeError("403 secondary rate limit")

    monkeypatch.setattr(github, "get_json", fake_get_json)
    # 不抛异常，返回空列表（首页就失败，无已收集候选）
    assert github.discover(min_stars=5000, max_scan=10) == []
