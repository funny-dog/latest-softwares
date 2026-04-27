"""Steam 客户端版本号 + 固定下载链接抓取器。

Steam 的下载链接是固定的稳定 URL（永远指向最新版），由 packages.yaml 写死。
版本号从 Valve 内部客户端自更新 API 获取。

API 端点：https://client-update.akamai.steamstatic.com/steam_client_win32
返回 Valve KeyValues 格式，version 字段为 Unix 时间戳（构建号）。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import requests

from ..http import get
from .base import AssetInfo, FetchError, FetchResult

API_URL = "https://client-update.akamai.steamstatic.com/steam_client_win32"
TIMEOUT = 30

# 匹配 KeyValues 格式中的 version 字段，如 "version"  "1769731672"
_VERSION_RE = re.compile(r'"version"\s+"(\d+)"')


def fetch(args: dict[str, Any]) -> FetchResult:
    assets: list[AssetInfo] = []
    version: str | None = None

    # 从 API 获取版本号
    try:
        resp = get(API_URL, timeout=TIMEOUT)
        resp.raise_for_status()
        match = _VERSION_RE.search(resp.text)
        if not match:
            raise FetchError("steam: 未能从 API 响应中提取 version 字段")
        ts = int(match.group(1))
        version = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except requests.RequestException as exc:
        raise FetchError(f"steam: API 请求失败：{exc}") from exc

    # 下载链接由 packages.yaml 的 args.platforms 提供（固定 URL 模式）
    for spec in args.get("platforms", []):
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=spec["download_url"],
            )
        )

    if not assets:
        raise FetchError("steam: platforms 不能为空")

    return FetchResult(
        id="",
        name="Steam",
        version=version or "unknown",
        source="Valve Client Update API",
        homepage="https://store.steampowered.com/about/",
        notes_url="https://store.steampowered.com/news/",
        assets=assets,
    )
