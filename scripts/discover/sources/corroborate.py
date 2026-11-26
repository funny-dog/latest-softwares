"""佐证源：用 GitHub Code Search 在 winget-pkgs / Scoop 仓库里搜候选的 repo URL。

total_count > 0 即表示该软件已被 winget/Scoop 收录 → 多源交叉验证通过。
任何失败都视为"未佐证"（False），绝不抛异常。
"""

from __future__ import annotations

from urllib.parse import quote

from ...net import get_json, github_headers
from ..models import Candidate
from . import brew as brew_source
from . import winget as winget_source

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 30
_WINGET_REPO = "microsoft/winget-pkgs"
_SCOOP_REPOS = ("ScoopInstaller/Main", "ScoopInstaller/Extras")


def _code_search_hits(repo_url_fragment: str, in_repo: str) -> int:
    q = quote(f'"{repo_url_fragment}" repo:{in_repo}')
    url = f"{_GITHUB_API}/search/code?q={q}"
    try:
        data = get_json(url, headers=github_headers(), timeout=_TIMEOUT)
        return int(data.get("total_count", 0)) if isinstance(data, dict) else 0
    except Exception:
        return 0


def corroborated_by_winget(repo: str) -> bool:
    fragment = f"github.com/{repo}"
    return _code_search_hits(fragment, _WINGET_REPO) > 0


def corroborated_by_scoop(repo: str) -> bool:
    fragment = f"github.com/{repo}"
    return any(_code_search_hits(fragment, r) > 0 for r in _SCOOP_REPOS)


def is_corroborated(repo: str) -> bool:
    """winget 或 Scoop 任一命中即视为多源佐证（winget 优先，命中短路）。"""
    if corroborated_by_winget(repo):
        return True
    return corroborated_by_scoop(repo)


def cross_reference_popular(
    candidates: list[Candidate],
    *,
    use_winget_index: bool = True,
    use_brew_catalog: bool = True,
    max_winget_lookups: int = 40,
) -> list[Candidate]:
    """用本地索引（WinGet source2.msix + Homebrew cask.json）为候选补全跨源证据。

    不消费 GitHub Search/Code API 额度；返回新发现的对应 WinGet/Brew Candidate 列表，
    由上层 aggregate.select_candidates 按 repo/homepage 聚合。
    """
    if not candidates:
        return []

    extra: list[Candidate] = []
    if use_brew_catalog:
        try:
            extra.extend(brew_source.cross_reference_brew(candidates))
        except Exception:
            pass
    if use_winget_index:
        try:
            extra.extend(
                winget_source.corroborate_with_winget_index(
                    candidates, max_lookups=max_winget_lookups
                )
            )
        except Exception:
            pass
    return extra
