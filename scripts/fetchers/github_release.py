"""通用 GitHub Release 抓取器。

支持两种模式：
  1. 简单模式：repo 直接调 /releases/latest（v2rayN / LocalSend / Codex）
  2. 过滤模式：给 tag_pattern 时遍历最近若干 release，
     按正则筛选出感兴趣的子产品（用于 Bitwarden 的 monorepo）

asset 匹配用 fnmatch（shell 通配符），比正则直观，用户配 yaml 时不易写错。
"""
from __future__ import annotations

import fnmatch
import os
import re
from typing import Any

import requests

from .base import AssetInfo, FetchError, FetchResult


GITHUB_API = "https://api.github.com"
TIMEOUT = 30


def _headers() -> dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "latest-softwares-sync",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _pick_release(repo: str, tag_pattern: str | None) -> dict[str, Any]:
    """tag_pattern 为空时返回 latest，否则在最近 30 个 release 里找首个匹配的。"""
    if not tag_pattern:
        url = f"{GITHUB_API}/repos/{repo}/releases/latest"
        resp = requests.get(url, headers=_headers(), timeout=TIMEOUT)
        if resp.status_code == 404:
            raise FetchError(f"{repo}: 仓库无 latest release（可能仅有 prerelease）")
        resp.raise_for_status()
        return resp.json()

    pattern = re.compile(tag_pattern)
    url = f"{GITHUB_API}/repos/{repo}/releases?per_page=30"
    resp = requests.get(url, headers=_headers(), timeout=TIMEOUT)
    resp.raise_for_status()
    for rel in resp.json():
        if rel.get("prerelease") or rel.get("draft"):
            continue
        if pattern.search(rel.get("tag_name", "")):
            return rel
    raise FetchError(f"{repo}: 最近 30 个 release 中没有匹配 {tag_pattern} 的稳定版")


def _extract_version(tag: str) -> str:
    """从 tag 提取裸版本号：v6.42 → 6.42；desktop-v2024.1.0 → 2024.1.0"""
    m = re.search(r"(\d[\w.\-]*)$", tag)
    return m.group(1) if m else tag


def fetch(args: dict[str, Any]) -> FetchResult:
    repo = args["repo"]
    tag_pattern = args.get("tag_pattern")
    asset_specs = args.get("assets", [])
    if not asset_specs:
        raise FetchError(f"{repo}: 至少要配置一个 asset 匹配规则")

    rel = _pick_release(repo, tag_pattern)
    tag = rel["tag_name"]
    version = _extract_version(tag)
    release_assets = rel.get("assets", [])

    matched: list[AssetInfo] = []
    for spec in asset_specs:
        platform = spec["platform"]
        pattern = spec["pattern"]
        hit = next(
            (a for a in release_assets if fnmatch.fnmatch(a["name"], pattern)),
            None,
        )
        if hit is None:
            # 单个 platform 没匹配到时不抛错，留空让后续 fetcher 继续；
            # 调用方可看到 assets 数量少了从而判断
            continue
        matched.append(AssetInfo(
            platform=platform,
            url=hit["browser_download_url"],
            filename=hit["name"],
            size=hit.get("size"),
        ))

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
    )
