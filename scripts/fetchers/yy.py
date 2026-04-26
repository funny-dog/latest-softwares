"""YY 语音下载链接抓取器。

YY 语音为 Windows 独占应用，下载页为 SPA，无公开版本 API。
版本号取当天日期（表示数据同步日期），下载链接指向官方下载页。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import AssetInfo, FetchResult


DOWNLOAD_PAGE = "https://www.yy.com/"


def fetch(args: dict[str, Any]) -> FetchResult:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    assets: list[AssetInfo] = []
    for spec in args.get("platforms", []):
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=spec["download_url"],
            )
        )

    if not assets:
        assets.append(AssetInfo(platform="win-x64", url=DOWNLOAD_PAGE))

    return FetchResult(
        id="yy",
        name="YY 语音",
        version=today,
        source="手动同步（无 API）",
        homepage=DOWNLOAD_PAGE,
        notes_url=DOWNLOAD_PAGE,
        assets=assets,
    )
