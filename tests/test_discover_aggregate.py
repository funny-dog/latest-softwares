from __future__ import annotations

from scripts.discover import aggregate
from scripts.discover.models import Candidate


def _cand(repo, stars, assets):
    return Candidate(
        repo=repo,
        name=repo.split("/")[-1],
        stars=stars,
        description="",
        asset_names=assets,
    )


def test_select_filters_and_sorts(monkeypatch):
    cands = [
        _cand("a/low", 6000, ["a-1.0-win-x64.exe"]),
        _cand("b/high", 9000, ["b-1.0-windows-installer.exe"]),
        _cand("c/nowin", 8000, ["c-1.0-linux.AppImage"]),  # 无 Windows 资产 → 淘汰
        _cand("d/exists", 9999, ["d-1.0-setup.exe"]),  # 已存在 → 淘汰
    ]
    monkeypatch.setattr(aggregate, "existing_repos", lambda: {"d/exists"})
    monkeypatch.setattr(aggregate, "is_corroborated", lambda repo: True)

    selected = aggregate.select_candidates(cands, max_output=10, max_corroborate=30)
    repos = [c.repo for c, _ in selected]
    assert repos == ["b/high", "a/low"]  # 按 star 降序，且各自带 pattern
    # 每个返回 (candidate, pattern)
    assert all(pattern for _, pattern in selected)


def test_select_requires_corroboration(monkeypatch):
    cands = [_cand("a/b", 9000, ["a-1.0-win-x64.exe"])]
    monkeypatch.setattr(aggregate, "existing_repos", lambda: set())
    monkeypatch.setattr(aggregate, "is_corroborated", lambda repo: False)  # 未佐证
    assert aggregate.select_candidates(cands, max_output=10, max_corroborate=30) == []


def test_select_respects_max_output(monkeypatch):
    cands = [_cand(f"o/r{i}", 9000 - i, [f"r{i}-1.0-setup.exe"]) for i in range(20)]
    monkeypatch.setattr(aggregate, "existing_repos", lambda: set())
    monkeypatch.setattr(aggregate, "is_corroborated", lambda repo: True)
    selected = aggregate.select_candidates(cands, max_output=10, max_corroborate=30)
    assert len(selected) == 10
