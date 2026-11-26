from __future__ import annotations

import io
import sqlite3
import tempfile
import os
import zipfile
from pathlib import Path
from typing import Any

import pytest

from scripts import discover_popular
from scripts.discover import aggregate
from scripts.discover.models import Candidate
from scripts.discover.review import ReviewManager
from scripts.discover.sources import brew, flathub, winget
from scripts.discover.state import DiscoveryState


def _build_winget_msix_bytes(
    rows: list[tuple[str, str, str | None, str, list[str], list[str]]],
) -> bytes:
    """构造内存中的 WinGet source2.msix（ZIP + Public/index.db SQLite）测试夹具。"""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE TABLE packages (rowid INTEGER PRIMARY KEY, id TEXT NOT NULL, "
                "name TEXT NOT NULL, moniker TEXT, latest_version TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE norm_names2 (norm_name TEXT NOT NULL, package INT64 NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE norm_publishers2 (norm_publisher TEXT NOT NULL, package INT64 NOT NULL)"
            )
            for idx, (pkg_id, name, moniker, ver, nnames, npubs) in enumerate(rows, 1):
                conn.execute(
                    "INSERT INTO packages (rowid, id, name, moniker, latest_version) VALUES (?, ?, ?, ?, ?)",
                    (idx, pkg_id, name, moniker, ver),
                )
                for nn in nnames:
                    conn.execute(
                        "INSERT INTO norm_names2 (norm_name, package) VALUES (?, ?)",
                        (nn, idx),
                    )
                for np in npubs:
                    conn.execute(
                        "INSERT INTO norm_publishers2 (norm_publisher, package) VALUES (?, ?)",
                        (np, idx),
                    )
            conn.commit()
        finally:
            conn.close()
        db_bytes = Path(db_path).read_bytes()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Public/index.db", db_bytes)
    return buf.getvalue()


class _FakeResponse:
    def __init__(
        self, text: str = "", *, status_code: int = 200, content: bytes = b""
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.content = content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Homebrew 30d Analytics Tests
# ---------------------------------------------------------------------------


def test_brew_discover_popular_ranks_filters_and_enriches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analytics_payload = {
        "category": "cask-install",
        "items": [
            {"number": 1, "cask": "existing-cask", "count": "999,000"},
            {"number": 2, "cask": "thirdparty/tap/foo", "count": "800,000"},
            {"number": 3, "cask": "temurin@17", "count": "700,000"},
            {"number": 4, "cask": "font-jetbrains-mono-nerd-font", "count": "650,000"},
            {"number": 5, "cask": "rejected-cask", "count": "600,000"},
            {"number": 5, "cask": "claude", "count": "42,787"},
            {"number": 6, "cask": "raycast", "count": "55,000"},
            {"number": 7, "cask": "disabled-app", "count": "50,000"},
        ],
    }
    cask_details: dict[str, dict[str, Any]] = {
        "raycast": {
            "token": "raycast",
            "name": ["Raycast"],
            "desc": "Control your tools with a few keystrokes",
            "homepage": "https://raycast.com/",
            "url": "https://releases.raycast.com/download-arm64.dmg",
            "disabled": False,
        },
        "claude": {
            "token": "claude",
            "name": ["Claude"],
            "desc": "AI assistant desktop app",
            "homepage": "https://claude.ai/",
            "url": "https://storage.googleapis.com/claude-universal.dmg",
            "disabled": False,
        },
        "disabled-app": {
            "token": "disabled-app",
            "name": ["Disabled App"],
            "homepage": "https://disabled.example/",
            "url": "https://disabled.example/app.dmg",
            "disabled": True,
        },
    }
    called_tokens: list[str] = []

    def fake_get_json(url: str, **kwargs: Any) -> Any:
        if "analytics/cask-install/30d.json" in url:
            return analytics_payload
        for tok, payload in cask_details.items():
            if url.endswith(f"/cask/{tok}.json"):
                called_tokens.append(tok)
                return payload
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(brew, "get_json", fake_get_json)

    state = DiscoveryState()
    state.rejected = ["brew:rejected-cask"]

    cands = brew.discover_popular(
        max_scan=5,
        state=state,
        existing_id_set={"existing-id"},
        existing_brew_ids={"existing-cask"},
        existing_homepage_set=set(),
        existing_repo_set=set(),
    )

    # 跳过 existing-cask, thirdparty/tap/foo, temurin@17, rejected-cask；disabled-app 被丢弃
    assert set(called_tokens) == {"raycast", "disabled-app", "claude"}
    assert [c.external_id for c in cands] == ["brew:raycast", "brew:claude"]
    assert cands[0].popularity == 55000
    assert cands[0].platform == "mac-arm64"
    assert cands[1].popularity == 42787
    assert cands[1].platform == "mac-universal"
    assert cands[0].evidences[0]["installs_30d"] == 55000


def test_brew_discover_popular_via_discover_flag_and_error_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        brew,
        "get_json",
        lambda url, **kw: (_ for _ in ()).throw(RuntimeError("analytics 503")),
    )
    state = DiscoveryState()
    cands = brew.discover(max_scan=5, state=state, popular=True)
    assert cands == []
    assert brew.LAST_ERROR == "analytics 503"
    assert "brew:analytics:30d" in state.retries


def test_brew_cross_reference_matches_by_repo_or_homepage() -> None:
    casks = [
        {
            "token": "heroic",
            "name": ["Heroic"],
            "desc": "Open source game launcher",
            "homepage": "https://heroicgameslauncher.com/",
            "url": "https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/releases/download/v2.0/Heroic-2.0.dmg",
            "disabled": False,
        }
    ]
    flathub_cand = Candidate(
        name="Heroic",
        repo="Heroic-Games-Launcher/HeroicGamesLauncher",
        homepage_url="https://heroicgameslauncher.com",
        source="flathub",
        external_id="flathub:com.heroicgameslauncher.hgl",
        popularity=82229,
    )
    matched = brew.cross_reference_brew([flathub_cand], casks=casks)
    assert len(matched) == 1
    assert matched[0].external_id == "brew:heroic"
    assert matched[0].popularity == 82229


# ---------------------------------------------------------------------------
# Flathub Popular / Trending Tests
# ---------------------------------------------------------------------------


def test_flathub_discover_merges_popular_trending_and_enriches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    popular_payload = {
        "hits": [
            {
                "app_id": "org.mozilla.firefox",
                "name": "Firefox",
                "installs_last_month": 200000,
                "verification_website": "mozilla.org",
            },
            {
                "app_id": "com.heroicgameslauncher.hgl",
                "name": "Heroic",
                "summary": "A games launcher",
                "installs_last_month": 82229,
                "trending": 12.5,
                "verification_website": "heroicgameslauncher.com",
                "main_categories": ["Game"],
            },
            {
                "app_id": "org.rejected.App",
                "name": "Rejected App",
                "installs_last_month": 90000,
            },
        ]
    }
    trending_payload = {
        "hits": [
            {
                "app_id": "com.heroicgameslauncher.hgl",
                "name": "Heroic",
                "installs_last_month": 82229,
            },
            {
                "app_id": "com.usebruno.Bruno",
                "name": "Bruno",
                "summary": "Opensource IDE for exploring APIs",
                "installs_last_month": 35000,
                "trending": 40.0,
                "main_categories": ["Development"],
            },
        ]
    }
    appstreams: dict[str, dict[str, Any]] = {
        "com.heroicgameslauncher.hgl": {
            "id": "com.heroicgameslauncher.hgl",
            "name": "Heroic",
            "summary": "An Open Source GOG, Epic and Amazon Prime Games Launcher",
            "categories": ["Game"],
            "urls": {
                "homepage": "https://heroicgameslauncher.com",
                "bugtracker": "https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/issues",
            },
        },
        "com.usebruno.Bruno": {
            "id": "com.usebruno.Bruno",
            "name": "Bruno",
            "summary": "Fast Git-friendly API client",
            "categories": ["Development"],
            "urls": {
                "homepage": "https://www.usebruno.com",
                "vcs_browser": "https://github.com/usebruno/bruno",
            },
        },
    }
    fetched_appstreams: list[str] = []

    def fake_get_json(url: str, **kwargs: Any) -> Any:
        if url.endswith("/collection/popular"):
            return popular_payload
        if url.endswith("/collection/trending"):
            return trending_payload
        for app_id, payload in appstreams.items():
            if url.endswith(f"/appstream/{app_id}"):
                fetched_appstreams.append(app_id)
                return payload
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(flathub, "get_json", fake_get_json)

    state = DiscoveryState()
    state.rejected = ["flathub:org.rejected.App"]

    cands = flathub.discover(
        max_scan=10,
        state=state,
        existing_id_set={"firefox"},
        existing_homepage_set=set(),
        existing_repo_set=set(),
    )

    assert fetched_appstreams == ["com.heroicgameslauncher.hgl", "com.usebruno.Bruno"]
    assert [c.external_id for c in cands] == [
        "flathub:com.heroicgameslauncher.hgl",
        "flathub:com.usebruno.Bruno",
    ]
    assert cands[0].repo == "Heroic-Games-Launcher/HeroicGamesLauncher"
    assert cands[0].homepage == "https://heroicgameslauncher.com"
    assert cands[0].popularity == 82229
    assert cands[1].repo == "usebruno/bruno"
    assert cands[1].popularity == 35000


def test_flathub_ignores_flathub_packaging_repo_and_degrades_on_trending_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get_json(url: str, **kwargs: Any) -> Any:
        if url.endswith("/collection/popular"):
            return {
                "hits": [
                    {
                        "app_id": "io.example.Tool",
                        "name": "Example Tool",
                        "installs_last_month": 5000,
                    }
                ]
            }
        if url.endswith("/collection/trending"):
            raise RuntimeError("trending timeout")
        if url.endswith("/appstream/io.example.Tool"):
            return {
                "name": "Example Tool",
                "summary": "Tool",
                "urls": {
                    "homepage": "https://exampletool.org",
                    "bugtracker": "https://github.com/flathub/io.example.Tool/issues",
                },
            }
        raise AssertionError(url)

    monkeypatch.setattr(flathub, "get_json", fake_get_json)

    state = DiscoveryState()
    cands = flathub.discover(
        max_scan=5,
        state=state,
        existing_id_set=set(),
        existing_homepage_set=set(),
        existing_repo_set=set(),
    )
    assert len(cands) == 1
    assert cands[0].repo == ""
    assert cands[0].homepage == "https://exampletool.org"
    assert flathub.LAST_ERROR is None


# ---------------------------------------------------------------------------
# WinGet source2.msix Index Lookup & Corroboration Tests
# ---------------------------------------------------------------------------


def test_winget_index_parse_lookup_and_publisher_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    msix_bytes = _build_winget_msix_bytes(
        [
            (
                "OpenAI.ChatGPT",
                "ChatGPT",
                "chatgpt",
                "26.1120.0",
                ["chatgpt"],
                ["openai"],
            ),
            (
                "lencx.ChatGPT",
                "ChatGPT by lencx",
                None,
                "1.1.0",
                ["chatgpt"],
                ["lencx"],
            ),
            (
                "Discord.Discord.arm64",
                "Discord (arm64)",
                "discord",
                "1.0.62",
                ["discord"],
                ["discord"],
            ),
            (
                "Discord.Discord",
                "Discord",
                "discord",
                "1.0.9270",
                ["discord"],
                ["discord"],
            ),
            (
                "Anthropic.Claude",
                "Claude",
                "claude",
                "1.2.3",
                ["claude"],
                ["anthropicpbc"],
            ),
        ]
    )

    index = winget.parse_winget_index_msix(msix_bytes)
    # 主条目优先于 .arm64 变体，精确 moniker 优先
    discord_hits = index.lookup("Discord")
    assert [e.id for e in discord_hits] == ["Discord.Discord", "Discord.Discord.arm64"]

    openai_hits = index.lookup("ChatGPT", publisher="OpenAI")
    assert [e.id for e in openai_hits] == ["OpenAI.ChatGPT"]

    pub_hits = index.lookup_by_publisher("AnthropicPBC")
    assert [e.id for e in pub_hits] == ["Anthropic.Claude"]

    # 测试 search_winget_by_publisher 拉取 raw YAML
    claude_installer = (
        "PackageIdentifier: Anthropic.Claude\n"
        "PackageVersion: 1.2.3\n"
        "Installers:\n"
        "  - Architecture: x64\n"
        "    InstallerUrl: https://downloads.claude.ai/Claude-Setup-x64.exe\n"
    )
    claude_locale = (
        "PackageIdentifier: Anthropic.Claude\n"
        "PackageName: Claude\n"
        "PackageUrl: https://claude.ai/\n"
        "ShortDescription: AI assistant\n"
    )

    def fake_get(url: str, **kwargs: Any) -> _FakeResponse:
        if url.endswith("Anthropic.Claude.installer.yaml"):
            return _FakeResponse(claude_installer)
        if url.endswith("Anthropic.Claude.locale.en-US.yaml"):
            return _FakeResponse(claude_locale)
        return _FakeResponse("", status_code=404)

    monkeypatch.setattr(winget, "get", fake_get)

    pub_cands = winget.search_winget_by_publisher("AnthropicPBC", index=index)
    assert len(pub_cands) == 1
    assert pub_cands[0].external_id == "Anthropic.Claude"
    assert (
        pub_cands[0].download_url == "https://downloads.claude.ai/Claude-Setup-x64.exe"
    )
    assert pub_cands[0].homepage_url == "https://claude.ai/"


def test_winget_corroborate_verifies_identity_and_rejects_homonym(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    msix_bytes = _build_winget_msix_bytes(
        [
            ("lencx.ChatGPT", "ChatGPT", None, "1.1.0", ["chatgpt"], ["lencx"]),
            (
                "OpenAI.ChatGPT",
                "ChatGPT",
                "chatgpt",
                "26.1120.0",
                ["chatgpt"],
                ["openai"],
            ),
        ]
    )
    index = winget.parse_winget_index_msix(msix_bytes)

    manifests: dict[str, str] = {
        "lencx.ChatGPT.installer.yaml": (
            "PackageIdentifier: lencx.ChatGPT\n"
            "Installers:\n"
            "  - Architecture: x64\n"
            "    InstallerUrl: https://github.com/lencx/ChatGPT/releases/download/v1.1.0/ChatGPT.msi\n"
        ),
        "lencx.ChatGPT.locale.en-US.yaml": (
            "PackageIdentifier: lencx.ChatGPT\n"
            "PackageName: ChatGPT\n"
            "PackageUrl: https://github.com/lencx/ChatGPT\n"
        ),
        "OpenAI.ChatGPT.installer.yaml": (
            "PackageIdentifier: OpenAI.ChatGPT\n"
            "Installers:\n"
            "  - Architecture: x64\n"
            "    InstallerUrl: https://persistent.oaistatic.com/sidekick/public/ChatGPT.msix\n"
        ),
        "OpenAI.ChatGPT.locale.en-US.yaml": (
            "PackageIdentifier: OpenAI.ChatGPT\n"
            "PackageName: ChatGPT\n"
            "PackageUrl: https://chatgpt.com/\n"
        ),
    }

    def fake_get(url: str, **kwargs: Any) -> _FakeResponse:
        for suffix, body in manifests.items():
            if url.endswith(suffix):
                return _FakeResponse(body)
        return _FakeResponse("", status_code=404)

    monkeypatch.setattr(winget, "get", fake_get)

    brew_chatgpt = Candidate(
        name="ChatGPT",
        homepage_url="https://chatgpt.com/",
        download_url="https://persistent.oaistatic.com/sidekick/public/ChatGPT.dmg",
        source="brew",
        external_id="brew:chatgpt",
        platform="mac",
        popularity=38077,
    )

    matched = winget.corroborate_with_winget_index(
        [brew_chatgpt], index=index, max_lookups=10
    )
    assert len(matched) == 1
    assert matched[0].external_id == "OpenAI.ChatGPT"
    assert matched[0].popularity == 38077


# ---------------------------------------------------------------------------
# Aggregate & CLI Popularity Integration Tests
# ---------------------------------------------------------------------------


def test_aggregate_merges_flathub_with_winget_and_sorts_by_popularity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "existing_ids",
        "existing_repos",
        "existing_homepages",
        "existing_source_ids",
    ):
        monkeypatch.setattr(aggregate, name, lambda: set())

    # Flathub 候选（无直链，homepage 为自定义域名，但 repo 与 WinGet 相同）
    flathub_heroic = Candidate(
        name="Heroic",
        repo="Heroic-Games-Launcher/HeroicGamesLauncher",
        homepage_url="https://heroicgameslauncher.com",
        download_url="",
        source="flathub",
        external_id="flathub:com.heroicgameslauncher.hgl",
        platform="linux-x64",
        popularity=82229,
    )
    # WinGet 匹配候选（homepage 为 GitHub repo URL，应识别为同一项目而非冲突）
    winget_heroic = Candidate(
        name="Heroic",
        repo="Heroic-Games-Launcher/HeroicGamesLauncher",
        homepage_url="https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher",
        download_url="https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/releases/download/v2.22.4/Heroic-Setup-2.22.4.exe",
        source="winget",
        external_id="HeroicGamesLauncher.HeroicGamesLauncher",
        platform="win-x64",
        link_kind="direct",
        fetcher="package_manifest",
        popularity=82229,
    )
    brew_low = Candidate(
        name="SmallTool",
        homepage_url="https://smalltool.example",
        download_url="https://smalltool.example/SmallTool.dmg",
        source="brew",
        external_id="brew:smalltool",
        platform="mac",
        fetcher="package_manifest",
        popularity=1200,
    )

    review = ReviewManager()
    selected = aggregate.select_candidates(
        [brew_low, flathub_heroic, winget_heroic],
        max_output=10,
        max_corroborate=0,
        review_manager=review,
    )

    assert len(selected) == 2
    top_cand, _ = selected[0]
    assert top_cand.name == "Heroic"
    assert set(top_cand.sources) == {"flathub", "winget"}
    assert top_cand.platform == "win-x64"
    assert top_cand.fetcher == "package_manifest"
    assert top_cand.homepage == "https://heroicgameslauncher.com"
    assert top_cand.manifest_ids() == {
        "winget": "HeroicGamesLauncher.HeroicGamesLauncher"
    }
    assert selected[1][0].name == "SmallTool"


def test_cli_popular_dry_run_does_not_mutate_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(discover_popular, "REPO_ROOT", tmp_path)

    out = tmp_path / "shared.yaml"
    out.write_text("packages: []\n", encoding="utf-8")
    state_f = tmp_path / "state.json"
    review_f = tmp_path / "review.json"
    ids_f = tmp_path / "new_ids.txt"

    brew_cand = Candidate(
        name="Raycast",
        homepage_url="https://raycast.com/",
        download_url="https://releases.raycast.com/Raycast-arm64.dmg",
        source="brew",
        external_id="brew:raycast",
        platform="mac-arm64",
        link_kind="direct",
        fetcher="package_manifest",
        description="Launcher for macOS",
        popularity=55000,
    )
    flathub_cand = Candidate(
        name="Bruno",
        repo="usebruno/bruno",
        homepage_url="https://www.usebruno.com",
        download_url="",
        source="flathub",
        external_id="flathub:com.usebruno.Bruno",
        platform="linux-x64",
        description="API client",
        popularity=35000,
    )
    winget_bruno = Candidate(
        name="Bruno",
        repo="usebruno/bruno",
        homepage_url="https://www.usebruno.com",
        download_url="https://github.com/usebruno/bruno/releases/download/v1.0/bruno_1.0_x64_win.exe",
        source="winget",
        external_id="Bruno.Bruno",
        platform="win-x64",
        link_kind="direct",
        fetcher="package_manifest",
        description="API client",
        popularity=35000,
    )

    seen_popular_flags: list[bool] = []

    def fake_fetch_source(src: str, **kw: Any) -> tuple[list[Candidate], str | None]:
        seen_popular_flags.append(bool(kw.get("popular")))
        if src == "brew":
            return [brew_cand], None
        if src == "flathub":
            return [flathub_cand], None
        return [], f"unexpected {src}"

    monkeypatch.setattr(discover_popular, "fetch_source", fake_fetch_source)
    monkeypatch.setattr(
        discover_popular,
        "cross_reference_popular",
        lambda cands, **kw: [winget_bruno],
    )
    for name in (
        "existing_ids",
        "existing_repos",
        "existing_homepages",
        "existing_source_ids",
    ):
        monkeypatch.setattr(aggregate, name, lambda: set())

    rc = discover_popular.main(
        [
            "--popular",
            "--dry-run",
            "--sources",
            "brew",
            "flathub",
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
    assert seen_popular_flags == [True, True]
    # --dry-run 不落盘任何文件
    assert out.read_text(encoding="utf-8") == "packages: []\n"
    assert not state_f.exists()
    assert not review_f.exists()
    assert not ids_f.exists()
