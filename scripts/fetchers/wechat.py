"""微信 PC 客户端下载链接抓取器。

腾讯为微信 Windows/Mac 维护了固定的重定向下载 URL，始终指向最新版安装包。
版本号通过抓取微信官网页面中的版本字符串获取；解析失败时回退到当天日期。
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import requests

from .base import AssetInfo, FetchResult


HOMEPAGE = "https://weixin.qq.com/"
TIMEOUT = 30
_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+(?:\.\d+)?)")


def fetch(args: dict[str, Any]) -> FetchResult:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    platforms = args.get("platforms", [])

    version = today
    try:
        resp = requests.get(
            HOMEPAGE,
            timeout=TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        resp.raise_for_status()
        m = _VERSION_RE.search(resp.text)
        if m:
            version = m.group(1)
    except requests.RequestException:
        pass  # 解析失败时使用日期作为版本号

    assets: list[AssetInfo] = []
    for spec in platforms:
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=spec["download_url"],
            )
        )

    if not assets:
        assets.append(
            AssetInfo(
                platform="win-x64",
                url="https://dldir1.qq.com/weixin/Windows/WeChatSetup.exe",
            )
        )

    return FetchResult(
        id="wechat",
        name="微信",
        version=version,
        source="微信官网",
        homepage=HOMEPAGE,
        notes_url=HOMEPAGE,
        assets=assets,
    )
