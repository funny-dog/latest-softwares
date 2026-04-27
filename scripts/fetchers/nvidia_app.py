"""NVIDIA App —— Windows 显卡管理与驱动更新工具。

NVIDIA App 下载页为 JavaScript SPA，无法从静态 HTML 提取版本号。
版本号取当天日期（表示数据同步日期），下载链接指向官方下载页。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .base import AssetInfo, FetchResult


DOWNLOAD_PAGE = "https://www.nvidia.com/en-us/software/nvidia-app/"


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
        id="nvidia-app",
        name="NVIDIA App",
        version=today,
        source="手动同步（无 API）",
        homepage=DOWNLOAD_PAGE,
        notes_url=DOWNLOAD_PAGE,
        assets=assets,
    )
