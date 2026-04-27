"""通用 GitHub Release 抓取器。

支持两种模式：
  1. 简单模式：repo 直接调 /releases/latest（v2rayN / LocalSend / Codex）
  2. 过滤模式：给 tag_pattern 时遍历最近若干 release，
     按正则筛选出感兴趣的子产品（用于 Bitwarden 的 monorepo）

asset 匹配用 fnmatch（shell 通配符），比正则直观，用户配 yaml 时不易写错。
"""

from __future__ import annotations

import fnmatch
import re
from typing import Any

from ..http import get_json, github_headers
from .base import AssetInfo, FetchError, FetchResult


GITHUB_API = "https://api.github.com"
TIMEOUT = 30
DEFAULT_RELEASE_SCAN_PAGES = 1


def _pick_release(
    repo: str,
    tag_pattern: str | None,
    release_scan_pages: int = DEFAULT_RELEASE_SCAN_PAGES,
) -> dict[str, Any]:
    """tag_pattern 为空时返回 latest，否则分页查找首个匹配的稳定版。"""
    if not tag_pattern:
        url = f"{GITHUB_API}/repos/{repo}/releases/latest"
        try:
            return get_json(url, headers=github_headers(), timeout=TIMEOUT)
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 404:
                raise FetchError(
                    f"{repo}: 仓库无 latest release（可能仅有 prerelease）"
                ) from exc
            raise

    pages = max(1, int(release_scan_pages))
    pattern = re.compile(tag_pattern)
    for page in range(1, pages + 1):
        url = f"{GITHUB_API}/repos/{repo}/releases?per_page=30&page={page}"
        releases = get_json(url, headers=github_headers(), timeout=TIMEOUT)
        if not releases:
            break
        for rel in releases:
            if rel.get("prerelease") or rel.get("draft"):
                continue
            if pattern.search(rel.get("tag_name", "")):
                return rel
    raise FetchError(
        f"{repo}: 最近 {pages * 30} 个 release 中没有匹配 {tag_pattern} 的稳定版"
    )


def _extract_version(tag: str) -> str:
    """从 tag 提取裸版本号：v6.42 → 6.42；desktop-v2024.1.0 → 2024.1.0"""
    m = re.search(r"(\d[\w.\-]*)$", tag)
    return m.group(1) if m else tag


def fetch(args: dict[str, Any]) -> FetchResult:
    repo = args["repo"]
    tag_pattern = args.get("tag_pattern")
    release_scan_pages = args.get("release_scan_pages", DEFAULT_RELEASE_SCAN_PAGES)
    asset_specs = args.get("assets", [])
    if not asset_specs:
        raise FetchError(f"{repo}: 至少要配置一个 asset 匹配规则")

    rel = _pick_release(repo, tag_pattern, release_scan_pages)
    tag = rel["tag_name"]
    version = _extract_version(tag)
    release_assets = rel.get("assets", [])

    matched: list[AssetInfo] = []
    warnings: list[str] = []
    for spec in asset_specs:
        platform = spec["platform"]
        pattern = spec["pattern"]
        hit = next(
            (a for a in release_assets if fnmatch.fnmatch(a["name"], pattern)),
            None,
        )
        if hit is None:
            warnings.append(f"{platform}: 没有匹配 asset pattern {pattern!r}")
            continue
        matched.append(
            AssetInfo(
                platform=platform,
                url=hit["browser_download_url"],
                filename=hit["name"],
                size=hit.get("size"),
            )
        )

    if not matched:
        raise FetchError(
            f"{repo}@{tag}: 没有任何 asset 匹配配置的 pattern，"
            f"现有 asset: {[a['name'] for a in release_assets][:5]}..."
        )

    return FetchResult(
        id="",  # 由 sync.py 覆盖
        name=repo.split("/")[-1],
        version=version,
        source=f"GitHub Release: {repo}",
        homepage=f"https://github.com/{repo}",
        released_at=rel.get("published_at"),
        notes_url=rel.get("html_url"),
        assets=matched,
        warnings=warnings,
    )
