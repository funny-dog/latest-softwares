"""把候选信息组装为 validate_config 认可的 package 条目。"""

from __future__ import annotations

import re

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
    repo: str,
    name: str,
    category: str,
    pattern: str,
    desc_en: str,
    desc_cn: str,
) -> dict:
    """按现有 YAML 字段顺序组装条目。"""
    return {
        "id": slugify(name),
        "name": name,
        "category": category,
        "editions": ["cn", "intl"],
        "homepage": f"https://github.com/{repo}",
        "fetcher": "github_release",
        "args": {
            "repo": repo,
            "assets": [{"platform": "win-x64", "pattern": pattern}],
        },
        "desc_cn": desc_cn,
        "desc_en": desc_en,
    }
