"""Geek Uninstaller 版本号 + 固定下载链接抓取器。

Geek Uninstaller 官方下载页面为 https://geekuninstaller.com/download，
下载链接需从页面抓取。
"""

from __future__ import annotations

import re
from typing import Any

import requests

from ..net import browser_headers, get
from .base import AssetInfo, FetchError, FetchResult


DOWNLOAD_PAGE = "https://geekuninstaller.com/download"
TIMEOUT = 30

_VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+\.\d+)\b")


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not platforms:
        raise FetchError("geek: platforms 不能为空")

    assets: list[AssetInfo] = []
    version: str | None = None

    try:
        resp = get(
            DOWNLOAD_PAGE,
            timeout=TIMEOUT,
            headers=browser_headers(),
        )
        resp.raise_for_status()
        text = resp.text
        found = _VERSION_RE.findall(text)
        if found:
            version = sorted(
                set(found), key=lambda x: tuple(map(int, x.split("."))), reverse=True
            )[0]
    except requests.RequestException as exc:
        raise FetchError(f"geek: 页面请求失败：{exc}") from exc

    for spec in platforms:
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=spec["download_url"],
            )
        )

    return FetchResult(
        id="geek",
        name="Geek Uninstaller",
        version=version or "unknown",
        source="Geek Uninstaller 官网",
        version_kind="release_version",
        version_source="official download page HTML",
        homepage="https://geekuninstaller.com/",
        notes_url="https://geekuninstaller.com/download",
        assets=assets,
    )
