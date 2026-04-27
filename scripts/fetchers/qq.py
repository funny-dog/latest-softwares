"""腾讯 QQ（QQNT）下载链接抓取器。

QQ 下载页为 JavaScript SPA，下载链接由 JS 动态生成，无公开版本 API。
版本号取当天日期（表示数据同步日期），下载链接指向官方下载页。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import AssetInfo, FetchResult


DOWNLOAD_PAGE = "https://im.qq.com/download/"


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
        id="qq",
        name="QQ",
        version=today,
        source="手动同步（无 API）",
        homepage="https://im.qq.com/",
        notes_url=DOWNLOAD_PAGE,
        assets=assets,
    )
