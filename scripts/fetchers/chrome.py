"""Google Chrome 版本号 + 固定下载链接抓取器。

Chrome 的下载链接对每个平台是**固定的稳定 URL**（永远指向最新稳定版），
所以下载链接不需要每次抓取，由 yaml 配置写死。
我们只需要从 versionhistory API 拉版本号和发布日期，渲染到 README。

API 文档：https://developer.chrome.com/docs/web-platform/version-history
端点：https://versionhistory.googleapis.com/v1/chrome/platforms/{os}/channels/{channel}/versions
"""
from __future__ import annotations

from typing import Any

import requests

from .base import AssetInfo, FetchError, FetchResult


API_TMPL = (
    "https://versionhistory.googleapis.com/v1/chrome/platforms/{os_key}"
    "/channels/{channel}/versions?pageSize=1"
)
TIMEOUT = 30


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not platforms:
        raise FetchError("chrome: platforms 不能为空")

    assets: list[AssetInfo] = []
    version: str | None = None

    for spec in platforms:
        platform = spec["platform"]
        os_key = spec["os_key"]
        channel = spec["channel"]
        download_url = spec["download_url"]

        if version is None:
            url = API_TMPL.format(os_key=os_key, channel=channel)
            resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "latest-softwares-sync"})
            resp.raise_for_status()
            payload = resp.json()
            versions = payload.get("versions", [])
            if not versions:
                raise FetchError(f"chrome: versionhistory 返回空（{os_key}/{channel}）")
            version = versions[0]["version"]

        assets.append(AssetInfo(platform=platform, url=download_url))

    return FetchResult(
        id="",
        name="Google Chrome",
        version=version or "unknown",
        source="Google Version History API",
        homepage="https://www.google.com/chrome/",
        notes_url="https://chromereleases.googleblog.com/",
        assets=assets,
    )
