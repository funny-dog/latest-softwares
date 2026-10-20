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


def test_budget_preserves_unscanned_items_on_same_page(monkeypatch):
    from scripts.discover.state import DiscoveryState

    items = [{"full_name": f"acme/app{i}", "stargazers_count": 9000} for i in range(3)]
    monkeypatch.setattr(
        github,
        "get_json",
        lambda url, **kw: (
            {"items": items, "total_count": 3}
            if "search/repositories" in url
            else {"assets": [{"name": "setup.exe"}]}
        ),
    )
    state = DiscoveryState()
    first = github.discover(max_scan=1, state=state)
    second = github.discover(max_scan=1, state=state)
    assert [c.repo for c in first + second] == ["acme/app0", "acme/app1"]
    assert state.get_cursor("github")["ranges"][0]["offset"] == 2


def test_large_search_is_partitioned_before_scanning(monkeypatch):
    from scripts.discover.state import DiscoveryState

    searches = []

    def get_json(url, **kwargs):
        if "search/repositories" not in url:
            return {"assets": [{"name": "setup.exe"}]}
        searches.append(url)
        if "stars:>=5000" in url:
            return {"total_count": 2000, "items": [{"stargazers_count": 20000}]}
        return {
            "total_count": 1,
            "items": [{"full_name": "acme/app", "stargazers_count": 19000}],
        }

    monkeypatch.setattr(github, "get_json", get_json)
    assert len(github.discover(max_scan=1, state=DiscoveryState())) == 1
    assert "stars:12501..20000" in searches[1]


def test_failed_release_is_retried_next_run_without_losing_cursor(monkeypatch):
    from scripts.discover.state import DiscoveryState

    state = DiscoveryState()
    monkeypatch.setattr(
        github,
        "get_json",
        lambda *a, **kw: {
            "items": [{"full_name": "acme/app", "stargazers_count": 9000}],
            "total_count": 1,
        },
    )
    monkeypatch.setattr(
        github,
        "_latest_release",
        lambda repo: (_ for _ in ()).throw(RuntimeError("temporary")),
    )
    assert github.discover(max_scan=1, state=state) == []
    state.retries["github:repo:acme/app"]["next_attempt"] = ""
    monkeypatch.setattr(
        github, "_latest_release", lambda repo: {"assets": [{"name": "setup.exe"}]}
    )
    assert github.discover(max_scan=1, state=state)[0].repo == "acme/app"
    assert "github:repo:acme/app" not in state.retries
