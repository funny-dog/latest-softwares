"""发现源：GitHub Search API 找高星 repo + 取 latest release 资产。"""

from __future__ import annotations

from typing import Any

from ...net import get_json, github_headers
from ..models import Candidate

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 30
_PER_PAGE = 50


def _latest_release(repo: str) -> dict[str, Any] | None:
    """获取指定 repo 的最新 release，失败时返回 None（无 release / 仅 prerelease → 跳过该 repo）。"""
    url = f"{_GITHUB_API}/repos/{repo}/releases/latest"
    try:
        return get_json(url, headers=github_headers(), timeout=_TIMEOUT)
    except Exception:
        return None


def discover(min_stars: int, max_scan: int) -> list[Candidate]:
    """按 star 降序扫描高星 repo，取得 latest release 资产，构建候选列表。"""
    candidates: list[Candidate] = []
    scanned = 0
    page = 1
    while scanned < max_scan:
        query = f"stars:>={min_stars}"
        url = (
            f"{_GITHUB_API}/search/repositories"
            f"?q={query}&sort=stars&order=desc&per_page={_PER_PAGE}&page={page}"
        )
        try:
            data = get_json(url, headers=github_headers(), timeout=_TIMEOUT)
        except Exception:
            # 限流（403 secondary rate limit）/ 网络抖动：用已收集的候选继续，
            # 不让单次 search 失败崩掉整轮（与管道其它网络调用的容错一致）。
            break
        items = data.get("items", []) if isinstance(data, dict) else []
        if not items:
            break
        for item in items:
            if scanned >= max_scan:
                break
            scanned += 1
            repo = item.get("full_name")
            if not repo:
                continue
            rel = _latest_release(repo)
            if rel is None:
                continue
            asset_names = [a["name"] for a in rel.get("assets", []) if a.get("name")]
            if not asset_names:
                continue
            candidates.append(
                Candidate(
                    repo=repo,
                    name=item.get("name") or repo.split("/")[-1],
                    stars=int(item.get("stargazers_count", 0)),
                    description=item.get("description") or "",
                    topics=list(item.get("topics") or []),
                    asset_names=asset_names,
                    released_at=rel.get("published_at"),
                )
            )
        # 返回项少于 per_page 说明已到最后一页
        if len(items) < _PER_PAGE:
            break
        page += 1
    return candidates
