from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import discover_popular
from scripts.discover.aggregate import select_candidates
from scripts.discover.generate import build_entry
from scripts.discover.models import Candidate
from scripts.discover.review import ReviewManager


@pytest.fixture(autouse=True)
def empty_catalog(monkeypatch):
    from scripts.discover import aggregate

    for name in (
        "existing_ids",
        "existing_repos",
        "existing_homepages",
        "existing_source_ids",
    ):
        monkeypatch.setattr(aggregate, name, lambda: set())


def test_multisource_merges_same_software_by_homepage():
    # 两个来源：一个来自 winget，一个来自 brew，具有相同的官方 homepage
    cand_winget = Candidate(
        name="VLC Media Player",
        homepage_url="https://www.videolan.org/vlc/",
        download_url="https://get.videolan.org/vlc/3.0.20/win64/vlc-3.0.20-win64.exe",
        source="winget",
        external_id="VideoLAN.VLC",
    )
    cand_brew = Candidate(
        name="vlc",
        homepage_url="https://videolan.org/vlc",
        download_url="https://get.videolan.org/vlc/3.0.20/macosx/vlc-3.0.20-intel64.dmg",
        source="brew",
        external_id="brew:vlc",
    )

    review = ReviewManager()
    selected = select_candidates(
        [cand_winget, cand_brew],
        max_output=10,
        max_corroborate=30,
        review_manager=review,
    )
    # 应当聚合为一个软件，而不是两个独立候选
    assert len(selected) == 1
    cand, _ = selected[0]
    assert set(cand.sources) == {"winget", "brew"}
    assert cand.homepage == "https://www.videolan.org/vlc/"
    assert len(cand.evidences) >= 2


def test_multisource_ambiguous_same_name_enters_review_not_picked():
    """同名但不同软件（repo 不同、homepage 不同）：

    遇到歧义不要随便取第一个，应记录到 review-file，且本轮不自动生成。
    """
    cand_a = Candidate(
        name="CoolApp",
        homepage_url="https://coolapp-corp.com",
        download_url="https://coolapp-corp.com/setup.exe",
        source="winget",
        external_id="Corp.CoolApp",
    )
    cand_b = Candidate(
        name="CoolApp",
        homepage_url="https://coolapp-community.org",
        download_url="https://coolapp-community.org/download.exe",
        source="scoop",
        external_id="scoop:coolapp",
    )

    review = ReviewManager()
    selected = select_candidates(
        [cand_a, cand_b],
        max_output=10,
        max_corroborate=30,
        review_manager=review,
    )
    # 遭遇歧义冲突，不随便选第一个，两个都不通过
    assert len(selected) == 0

    # review 记录了冲突
    conflict_entries = [e for e in review.entries if e.reason == "conflict"]
    assert len(conflict_entries) == 2
    assert any("同名歧义冲突" in e.detail for e in conflict_entries)


def test_no_reliable_link_enters_review():
    cand = Candidate(
        name="NoLinkTool",
        homepage_url="https://nolink.org",
        download_url="",  # 无有效下载链接且无 GitHub release 资产
        source="winget",
        external_id="NoLink.Tool",
    )
    review = ReviewManager()
    selected = select_candidates(
        [cand],
        max_output=10,
        max_corroborate=30,
        review_manager=review,
    )
    assert len(selected) == 0
    no_links = [e for e in review.entries if e.reason == "no_reliable_link"]
    assert len(no_links) == 1
    assert no_links[0].name == "NoLinkTool"


def test_build_entry_generates_download_page():
    entry = build_entry(
        name="Raycast",
        category="Utilities",
        homepage="https://www.raycast.com",
        download_url="https://releases.raycast.com/download.dmg",
        platform="mac-universal",
        desc_en="Productivity tool",
        desc_cn="macOS 效率启动器",
        fetcher="download_page",
    )
    assert entry["id"] == "raycast"
    assert entry["fetcher"] == "download_page"
    assert entry["homepage"] == "https://www.raycast.com"
    assert entry["args"]["platforms"] == [
        {
            "platform": "mac-universal",
            "download_url": "https://releases.raycast.com/download.dmg",
        }
    ]


def test_cli_all_sources_failed_returns_nonzero(tmp_path: Path, monkeypatch):
    """全源网络失败时，单源隔离不能伪装成成功零结果，全源失败返回非零。"""
    out = tmp_path / "shared.yaml"
    out.write_text("packages: []\n", encoding="utf-8")
    state_f = tmp_path / "state.json"
    review_f = tmp_path / "review.json"

    def fake_discover_fail(**kw):
        raise RuntimeError("GitHub API network outage")

    def fake_fetch_fail(src, **kw):
        return [], f"{src} network connection failed"

    monkeypatch.setattr(discover_popular, "discover", fake_discover_fail)
    monkeypatch.setattr(discover_popular, "fetch_source", fake_fetch_fail)

    rc = discover_popular.main(
        [
            "--sources",
            "github",
            "winget",
            "--output",
            str(out),
            "--state-file",
            str(state_f),
            "--review-file",
            str(review_f),
        ]
    )
    # 全源失败必须返回非零 exit code
    assert rc != 0


def test_cli_single_source_failure_isolated(tmp_path: Path, monkeypatch):
    """一个源失败，另一个源成功：流程正常继续，不伪装成零结果。"""
    out = tmp_path / "shared.yaml"
    out.write_text(
        "packages:\n"
        "- id: existing\n"
        "  name: Existing\n"
        "  category: Utilities\n"
        "  editions: [cn, intl]\n"
        "  fetcher: download_page\n"
        "  args:\n"
        "    platforms:\n"
        "    - platform: win-x64\n"
        "      download_url: https://example.com/existing.exe\n"
        "  desc_cn: 现有\n"
        "  desc_en: existing\n",
        encoding="utf-8",
    )
    state_f = tmp_path / "state.json"
    review_f = tmp_path / "review.json"
    ids_f = tmp_path / "new_ids.txt"

    # github 挂了
    def fake_discover_fail(**kw):
        raise RuntimeError("github timeout")

    # winget 成功发现候选
    cand = Candidate(
        name="Rufus WinGet",
        homepage_url="https://rufus.ie",
        download_url="https://github.com/pbatard/rufus/releases/download/v4.5/rufus-4.5.exe",
        source="winget",
        external_id="Rufus.Rufus",
        platform="win-x64",
    )

    def fake_fetch_source(src, **kw):
        if src == "winget":
            return [cand], None
        return [], "source failed"

    monkeypatch.setattr(discover_popular, "discover", fake_discover_fail)
    monkeypatch.setattr(discover_popular, "fetch_source", fake_fetch_source)
    monkeypatch.setattr(discover_popular, "categorize", lambda *a: "Utilities")
    monkeypatch.setattr(discover_popular, "translate_to_zh", lambda *a: "系统工具")

    rc = discover_popular.main(
        [
            "--sources",
            "github",
            "winget",
            "--output",
            str(out),
            "--state-file",
            str(state_f),
            "--review-file",
            str(review_f),
            "--new-ids-file",
            str(ids_f),
        ]
    )
    assert rc == 0
    assert "rufus-winget" in ids_f.read_text(encoding="utf-8")
    assert state_f.is_file()
    assert review_f.is_file()
    review_data = json.loads(review_f.read_text(encoding="utf-8"))
    assert "summary" in review_data


def test_conflicting_external_identity_enters_review():
    one = Candidate(
        name="Sample",
        source="winget",
        external_id="Publisher.One",
        homepage_url="https://example.test/sample",
        download_url="https://example.test/app.exe",
    )
    two = Candidate(
        name="Sample",
        source="winget",
        external_id="Publisher.Two",
        homepage_url="https://example.test/sample",
        download_url="https://example.test/app.exe",
    )
    review = ReviewManager()
    assert (
        select_candidates(
            [one, two], max_output=10, max_corroborate=0, review_manager=review
        )
        == []
    )
    assert review.entries[0].reason == "conflict"


def test_cli_generates_refreshable_manifest_and_retains_pending(tmp_path, monkeypatch):
    import yaml
    from scripts.discover.state import DiscoveryState

    out = tmp_path / "shared.yaml"
    out.write_text("packages: []\n")
    state_file = tmp_path / "state.json"
    candidate = Candidate(
        name="Sample App",
        source="brew",
        external_id="brew:sample",
        platform="mac-arm64",
        homepage_url="https://example.test/sample",
        download_url="https://example.test/app-arm64.dmg",
    )
    monkeypatch.setattr(
        discover_popular, "fetch_source", lambda *a, **kw: ([candidate], None)
    )
    monkeypatch.setattr(discover_popular, "translate_to_zh", lambda value: "测试软件")
    assert (
        discover_popular.main(
            [
                "--sources",
                "brew",
                "--output",
                str(out),
                "--state-file",
                str(state_file),
                "--review-file",
                str(tmp_path / "review.json"),
                "--new-ids-file",
                str(tmp_path / "ids"),
            ]
        )
        == 0
    )
    entry = yaml.safe_load(out.read_text())["packages"][0]
    assert entry["fetcher"] == "package_manifest"
    assert entry["args"] == {
        "provider": "brew",
        "package": "sample",
        "platforms": [{"platform": "mac-arm64"}],
    }
    assert entry["source_ids"] == {"brew": "sample"}
    assert DiscoveryState.load(state_file).pending[0]["external_id"] == "brew:sample"


def test_github_repo_suffix_is_removed_without_stripping_name_characters():
    from scripts.discover.url_utils import extract_github_repo, is_valid_http_url

    assert extract_github_repo("https://github.com/git/git") == "git/git"
    assert extract_github_repo("https://github.com/git/git.git") == "git/git"
    assert is_valid_http_url(
        "https://github.com/PowerShell/PowerShell/releases/download/v1/powershell.exe"
    )
