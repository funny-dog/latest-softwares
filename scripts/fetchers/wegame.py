"""WeGame 客户端 —— 下载链接指向官方下载页。

WeGame 无公开版本 API，官网为 SPA，下载链接由 JavaScript 动态生成。
版本号取当天日期（表示数据同步日期），下载链接指向官方下载页。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import AssetInfo, FetchResult

DOWNLOAD_PAGE = "https://www.wegame.com.cn/client/"


def fetch(args: dict[str, Any]) -> FetchResult:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    assets: list[AssetInfo] = []
    for spec in args.get("platforms", []):
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=DOWNLOAD_PAGE,
            )
        )

    if not assets:
        assets.append(AssetInfo(platform="win-x64", url=DOWNLOAD_PAGE))

    return FetchResult(
        id="",
        name="WeGame",
        version=today,
        source="手动同步（无 API）",
        homepage="https://www.wegame.com.cn/",
        notes_url=DOWNLOAD_PAGE,
        assets=assets,
    )
