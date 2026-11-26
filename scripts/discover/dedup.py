"""对照现有 packages/*.yaml 判断候选是否已收录。"""

from __future__ import annotations

from ..config_loader import load_packages_config
from .models import Candidate
from .url_utils import normalize_homepage


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


def existing_homepages() -> set[str]:
    """返回所有现有条目的规范化 homepage 集合。"""
    cfg = load_packages_config()
    homepages: set[str] = set()
    for pkg in cfg.get("packages", []):
        if not isinstance(pkg, dict):
            continue
        hp = pkg.get("homepage")
        if isinstance(hp, str) and hp.strip():
            norm = normalize_homepage(hp)
            if norm:
                homepages.add(norm)
    return homepages


def is_new(candidate: Candidate, existing: set[str]) -> bool:
    """判断候选 repo 是否未在现有清单中收录。"""
    if not candidate.repo:
        return True
    return candidate.repo.strip().lower() not in existing


def is_already_collected(
    candidate: Candidate,
    existing_repos_set: set[str],
    existing_homepages_set: set[str],
) -> bool:
    """综合 repo 与规范化 homepage 判断候选是否已被收录。"""
    if candidate.repo and candidate.repo.strip().lower() in existing_repos_set:
        return True
    norm_hp = normalize_homepage(candidate.homepage)
    if norm_hp and norm_hp in existing_homepages_set:
        return True
    return False


def existing_source_ids() -> set[tuple[str, str]]:
    """返回所有现有条目的 (provider, id_casefold) 集合（来自 source_ids 及 package_manifest args）。"""
    result: set[tuple[str, str]] = set()
    for p in load_packages_config().get("packages", []):
        if not isinstance(p, dict):
            continue
        for provider, ident in (p.get("source_ids") or {}).items():
            if isinstance(provider, str) and isinstance(ident, str) and ident.strip():
                result.add((provider.strip().lower(), ident.strip().casefold()))
        if p.get("fetcher") == "package_manifest":
            args = p.get("args") or {}
            if isinstance(args, dict):
                raw_sources = args.get("sources")
                specs = raw_sources if isinstance(raw_sources, list) else [args]
                for spec in specs:
                    if not isinstance(spec, dict):
                        continue
                    prov = spec.get("provider")
                    pkg = spec.get("package")
                    if isinstance(prov, str) and isinstance(pkg, str) and pkg.strip():
                        result.add((prov.strip().lower(), pkg.strip().casefold()))
    return result
