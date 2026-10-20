"""把候选信息组装为 validate_config 认可的 package 条目。"""

from __future__ import annotations

import re
from typing import Any

_NON_ID = re.compile(r"[^a-z0-9]+")
_LEADING_NON_ALNUM = re.compile(r"^[^a-z0-9]+")


def slugify(name: str) -> str:
    """转为合法 id：小写、非字母数字→连字符、去首尾连字符。

    需满足 validate_config 的 ID_RE: ^[a-z0-9][a-z0-9-]*$
    """
    s = name.strip().lower()
    s = _NON_ID.sub("-", s)
    s = _LEADING_NON_ALNUM.sub("", s)
    s = s.strip("-")
    return s


def build_entry(
    *,
    name: str,
    category: str,
    repo: str = "",
    pattern: str = "",
    desc_en: str = "",
    desc_cn: str = "",
    fetcher: str = "github_release",
    homepage: str = "",
    download_url: str = "",
    platform: str = "win-x64",
    link_kind: str | None = None,
    provider: str = "",
    package: str = "",
) -> dict:
    """按现有 YAML 字段规范组装条目。

    兼容 github_release（唯一可靠资产匹配）与 download_page（官方下载元数据）。
    """
    entry_id = slugify(name)
    resolved_homepage = homepage or (f"https://github.com/{repo}" if repo else "")

    if fetcher == "package_manifest":
        if provider not in {"winget", "brew", "scoop"} or not package:
            raise ValueError("package_manifest needs a known provider and package id")
        return {
            "id": entry_id,
            "name": name,
            "category": category,
            "editions": ["cn", "intl"],
            "homepage": resolved_homepage,
            "fetcher": fetcher,
            "args": {
                "provider": provider,
                "package": package,
                "platforms": [{"platform": platform}],
            },
            "desc_cn": desc_cn,
            "desc_en": desc_en,
        }

    if fetcher == "github_release" and repo and pattern:
        return {
            "id": entry_id,
            "name": name,
            "category": category,
            "editions": ["cn", "intl"],
            "homepage": resolved_homepage,
            "fetcher": "github_release",
            "args": {
                "repo": repo,
                "assets": [{"platform": platform, "pattern": pattern}],
            },
            "desc_cn": desc_cn,
            "desc_en": desc_en,
        }

    # 官方直链或非 GitHub 软件构建 download_page 条目
    platform_spec: dict[str, Any] = {
        "platform": platform,
        "download_url": download_url,
    }
    if link_kind in {"direct", "landing_page"}:
        platform_spec["link_kind"] = link_kind

    return {
        "id": entry_id,
        "name": name,
        "category": category,
        "editions": ["cn", "intl"],
        "homepage": resolved_homepage or download_url,
        "fetcher": "download_page",
        "args": {
            "platforms": [platform_spec],
        },
        "desc_cn": desc_cn,
        "desc_en": desc_en,
    }
