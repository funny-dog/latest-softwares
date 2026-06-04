"""版本 (edition) 过滤工具。

每个软件可属于一个或多个 edition：
  - cn   : 国内版（部署到阿里云）
  - intl : 国际版（部署到 FastAPI Cloud）

packages.yaml 中通过 editions 字段声明，缺省默认两个版本都包含。

说明：本模块原在 scripts/editions.py，现下沉到 app_core 作为共享内核的一部分，
让两版 API 后端都能用它而不必依赖 scripts/（国内版部署会排除 scripts/）。
scripts/editions.py 改为从这里 re-export，保持既有 import 路径不变。
"""

from __future__ import annotations

from typing import Any

VALID_EDITIONS = {"cn", "intl"}
DEFAULT_EDITIONS = sorted(VALID_EDITIONS)  # ["cn", "intl"]


def get_editions(entry: dict[str, Any]) -> list[str]:
    """从 packages.yaml 条目中获取 editions，缺省返回全部。"""
    editions = entry.get("editions")
    if not editions:
        return list(DEFAULT_EDITIONS)
    if isinstance(editions, str):
        return [editions]
    return list(editions)


def filter_by_edition(
    entries: list[dict[str, Any]],
    edition: str | None,
) -> list[dict[str, Any]]:
    """按 edition 过滤 packages 列表。edition=None 时不过滤。"""
    if edition is None:
        return entries
    return [e for e in entries if edition in get_editions(e)]


def filter_data_by_edition(data: dict[str, Any], edition: str | None) -> dict[str, Any]:
    """Filter a latest.json-style document by edition and keep stats consistent."""
    if edition is None:
        return data

    filtered = dict(data)
    packages = filter_by_edition(data.get("packages", []), edition)
    package_ids = {pkg.get("id") for pkg in packages}
    stats = dict(data.get("stats", {}))
    failures = [
        failure
        for failure in stats.get("failures", [])
        if failure.get("id") in package_ids
    ]
    failed_ids = [failure["id"] for failure in failures if failure.get("id")]

    stats["total"] = len(packages)
    stats["failed"] = len(failed_ids)
    stats["failed_ids"] = failed_ids
    if failures:
        stats["failures"] = failures
    else:
        stats.pop("failures", None)

    success = sum(1 for pkg in packages if not pkg.get("_stale"))
    stats["success"] = success

    filtered["packages"] = packages
    filtered["stats"] = stats
    filtered["edition"] = edition
    return filtered


def validate_editions(editions: object) -> str | None:
    """校验 editions 字段，返回错误信息或 None。"""
    if editions is None:
        return None  # 缺省合法
    if isinstance(editions, str):
        editions = [editions]
    if not isinstance(editions, list) or not editions:
        return "editions 必须是非空列表"
    for e in editions:
        if e not in VALID_EDITIONS:
            return f"editions 包含未知值 '{e}'，合法值: {sorted(VALID_EDITIONS)}"
    return None
