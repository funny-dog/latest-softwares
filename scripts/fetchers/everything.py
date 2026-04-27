"""Everything 版本号 + 固定下载链接抓取器。

Everything 官方下载页面为 https://www.voidtools.com/download.php，
下载链接格式固定，版本号从页面抓取。
"""

from __future__ import annotations

import re
from typing import Any

import requests

from ..net import browser_headers, get
from .base import AssetInfo, FetchError, FetchResult


DOWNLOAD_PAGE = "https://www.voidtools.com/download.php"
TIMEOUT = 30

_VERSION_RE = re.compile(r"Download Everything ([\d.]+)")


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not platforms:
        raise FetchError("everything: platforms 不能为空")

    assets: list[AssetInfo] = []
    version: str | None = None

    try:
        resp = get(
            DOWNLOAD_PAGE,
            timeout=TIMEOUT,
            headers=browser_headers(),
        )
        resp.raise_for_status()
        m = _VERSION_RE.search(resp.text)
        if m:
            version = m.group(1)
    except requests.RequestException as exc:
        raise FetchError(f"everything: 页面请求失败：{exc}") from exc

    for spec in platforms:
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=spec["download_url"],
            )
        )

    return FetchResult(
        id="everything",
        name="Everything",
        version=version or "unknown",
        source="voidtools 官网",
        homepage="https://www.voidtools.com/",
        notes_url="https://www.voidtools.com/download.php",
        assets=assets,
    )
