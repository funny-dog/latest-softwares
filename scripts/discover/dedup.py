"""对照现有 packages/*.yaml 判断候选是否已收录。"""

from __future__ import annotations

from ..config_loader import load_packages_config
from .models import Candidate


def existing_repos() -> set[str]:
    """返回现有 github_release 条目的 repo 集合（全小写）。"""
    cfg = load_packages_config()
    repos: set[str] = set()
    for pkg in cfg.get("packages", []):
        if not isinstance(pkg, dict):
            continue
        if pkg.get("fetcher") != "github_release":
            continue
        repo = (pkg.get("args") or {}).get("repo")
        if isinstance(repo, str) and repo.strip():
            repos.add(repo.strip().lower())
    return repos


def existing_ids() -> set[str]:
    """返回所有现有条目的 id 集合（不限 fetcher 类型）。

    用于防止 discover 生成的 slugified id 与任意 fetcher 的现有条目冲突，
    避免仅凭 repo 去重遗漏 download_page 等非 github_release 条目。
    """
    cfg = load_packages_config()
    ids: set[str] = set()
    for pkg in cfg.get("packages", []):
        if not isinstance(pkg, dict):
            continue
        pkg_id = pkg.get("id")
        if isinstance(pkg_id, str) and pkg_id.strip():
            ids.add(pkg_id.strip())
    return ids


def is_new(candidate: Candidate, existing: set[str]) -> bool:
    """判断候选 repo 是否未在现有清单中收录。"""
    return candidate.repo.strip().lower() not in existing
