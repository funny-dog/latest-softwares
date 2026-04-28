"""Everything 版本号 + 下载链接抓取器。

Everything 官方下载页面为 https://www.voidtools.com/download.php，
版本号从页面 "Download Everything X.Y.Z.W" 字样解析。

下载链接支持 `{version}` 占位符，由 fetcher 在解析到真实版本后填充，
避免 packages.yaml 里写死版本号导致与 README 显示版本脱节。
"""

from __future__ import annotations

import re
from typing import Any

import requests

from ..net import browser_headers, get
from .base import (
    VERSION_KIND_RELEASE,
    VERSION_SOURCE_OFFICIAL_PAGE_HTML,
    AssetInfo,
    FetchError,
    FetchResult,
)


DOWNLOAD_PAGE = "https://www.voidtools.com/download.php"
TIMEOUT = 30

_VERSION_RE = re.compile(r"Download Everything ([\d.]+)")


def _resolve_url(template: str, version: str) -> str:
    """把 {version} 占位符替换为真实版本；不含占位符则原样返回。"""
    if "{version}" not in template:
        return template
    return template.format(version=version)


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not platforms:
        raise FetchError("everything: platforms 不能为空")

    try:
        resp = get(
            DOWNLOAD_PAGE,
            timeout=TIMEOUT,
            headers=browser_headers(),
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"everything: 页面请求失败：{exc}") from exc

    m = _VERSION_RE.search(resp.text)
    if not m:
        raise FetchError("everything: 无法从下载页解析版本号")
    version = m.group(1)

    assets: list[AssetInfo] = []
    for spec in platforms:
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=_resolve_url(spec["download_url"], version),
                link_kind=spec.get("link_kind"),
            )
        )

    return FetchResult(
        id="everything",
        name="Everything",
        version=version,
        source="voidtools 官网",
        version_kind=VERSION_KIND_RELEASE,
        version_source=VERSION_SOURCE_OFFICIAL_PAGE_HTML,
        homepage="https://www.voidtools.com/",
        notes_url="https://www.voidtools.com/download.php",
        assets=assets,
    )
