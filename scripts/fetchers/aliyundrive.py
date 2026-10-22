"""读取阿里云盘官网明确声明的客户端 URL，不执行页面 JavaScript。"""

from __future__ import annotations

import re

from ..net import browser_headers, get
from .base import AssetInfo, FetchError, FetchResult, VERSION_SOURCE_OFFICIAL_PAGE_HTML

DOWNLOAD_PAGE = "https://www.alipan.com/download"
CLIENTS = {
    "win-x64": ("app_windows_download_link", ".exe"),
    "mac-x64": ("app_mac_download_link", ".dmg"),
    "mac-arm64": ("app_mac_arm64_download_link", "-arm64.dmg"),
}


def fetch(args: dict) -> FetchResult:
    response = get(DOWNLOAD_PAGE, headers=browser_headers(), stream=True, timeout=30)
    try:
        response.raise_for_status()
        html = response.raw.read(65536, decode_content=True).decode(
            "utf-8", errors="replace"
        )
    finally:
        response.close()
    assets = []
    versions = set()
    for spec in args["platforms"]:
        platform = spec["platform"]
        if platform not in CLIENTS:
            raise FetchError(f"unsupported Aliyun Drive platform: {platform}")
        field, suffix = CLIENTS[platform]
        matches = re.findall(
            rf"\b{field}\s*:\s*['\"]"
            rf"(https://cdn\.aliyundrive\.net/downloads/apps/desktop/aDrive-"
            rf"(\d+(?:\.\d+)+){re.escape(suffix)})['\"]",
            html,
        )
        if len(matches) != 1:
            raise FetchError(
                f"official Aliyun Drive client URL missing or ambiguous: {platform}"
            )
        url, version = matches[0]
        versions.add(version)
        assets.append(AssetInfo(platform=platform, url=url, link_kind="direct"))
    if len(versions) != 1:
        raise FetchError(
            "official Aliyun Drive client versions are inconsistent or missing"
        )
    return FetchResult(
        id="aliyundrive",
        name="阿里云盘",
        version=versions.pop(),
        version_source=VERSION_SOURCE_OFFICIAL_PAGE_HTML,
        source="Aliyun Drive official client download configuration",
        homepage="https://www.alipan.com/",
        notes_url=DOWNLOAD_PAGE,
        assets=assets,
    )
