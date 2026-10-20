from __future__ import annotations

from scripts.discover.sources import brew
from scripts.discover.state import DiscoveryState


def test_brew_infer_platform_with_and_without_arch_evidence():
    # 有明确 universal 证据
    p_uni, lk_uni = brew.infer_brew_platform(
        "https://example.com/app-universal.dmg", {}
    )
    assert p_uni == "mac-universal"
    assert lk_uni == "direct"

    # 有明确 arm64 证据
    p_arm, lk_arm = brew.infer_brew_platform("https://example.com/app-arm64.dmg", {})
    assert p_arm == "mac-arm64"
    assert lk_arm == "direct"

    # 有明确 x64 证据
    p_x64, lk_x64 = brew.infer_brew_platform("https://example.com/app-intel.dmg", {})
    assert p_x64 == "mac-x64"
    assert lk_x64 == "direct"

    # 无明确架构证据，标不含架构的 mac 平台与 landing_page
    p_none, lk_none = brew.infer_brew_platform(
        "https://example.com/download/app.dmg", {}
    )
    assert p_none == "mac"
    assert lk_none == "direct"


def test_brew_discover_parses_json_api(monkeypatch):
    fake_casks = [
        {
            "token": "test-browser",
            "name": ["Test Browser"],
            "desc": "A fast and secure browser",
            "homepage": "https://testbrowser.org",
            "url": "https://testbrowser.org/download/TestBrowser-universal.dmg",
            "version": "1.0.0",
        },
        {
            "token": "bad-script-app",
            "name": ["Bad Script"],
            "desc": "Script url app",
            "homepage": "https://bad.org",
            "url": "powershell -c evil",  # 非 http(s) 地址会被拒绝
        },
    ]

    def fake_get_json(url, **kwargs):
        assert "cask.json" in url
        return fake_casks

    monkeypatch.setattr(brew, "get_json", fake_get_json)

    state = DiscoveryState()
    cands = brew.discover(max_scan=10, state=state)

    assert len(cands) == 2
    valid_cand = cands[0]
    assert valid_cand.name == "Test Browser"
    assert valid_cand.external_id == "brew:test-browser"
    assert valid_cand.source == "brew"
    assert valid_cand.platform == "mac-universal"
    assert (
        valid_cand.download_url
        == "https://testbrowser.org/download/TestBrowser-universal.dmg"
    )
    assert valid_cand.homepage == "https://testbrowser.org"

    # bad url 项 download_url 应为空
    bad_cand = cands[1]
    assert bad_cand.download_url == ""


def test_brew_discover_cursor_advances(monkeypatch):
    fake_casks = [
        {
            "token": f"app-{i}",
            "name": [f"App {i}"],
            "url": f"https://example.com/app-{i}.dmg",
        }
        for i in range(5)
    ]
    monkeypatch.setattr(brew, "get_json", lambda *a, **kw: fake_casks)

    state = DiscoveryState()
    cands_first_batch = brew.discover(max_scan=2, state=state)
    assert len(cands_first_batch) == 2
    assert [c.name for c in cands_first_batch] == ["App 0", "App 1"]

    cursor = state.get_cursor("brew")
    assert cursor["cursor"] == 2

    cands_second_batch = brew.discover(max_scan=2, state=state)
    assert len(cands_second_batch) == 2
    assert [c.name for c in cands_second_batch] == ["App 2", "App 3"]


def test_brew_network_failure_isolated(monkeypatch):
    def fake_get_json(url, **kwargs):
        raise RuntimeError("brew api down")

    monkeypatch.setattr(brew, "get_json", fake_get_json)
    state = DiscoveryState()
    cands = brew.discover(max_scan=5, state=state)
    assert cands == []
    assert brew.LAST_ERROR == "brew api down"
