"""百度网盘版本号 + 固定下载链接抓取器。

百度网盘下载页 https://pan.baidu.com/disk/base/semdownload 是 SPA，
真正的客户端版本号通过 JS 异步加载，HTML 里只能拿到一个
``window.__V20_VER__`` 的页面构建时间戳（形如 ``4/24/2026, 2:55:02 PM``）。
我们把它解析并格式化成 ``YYYY-MM-DD`` 作为"页面更新时间"展示——
不是真正的客户端版本号，但至少能反映上游确实有动静。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import requests

from ..net import browser_headers, get
from .base import (
    VERSION_KIND_PAGE_DATE,
    VERSION_SOURCE_BAIDU_PAGE_TIMESTAMP,
    AssetInfo,
    FetchError,
    FetchResult,
)


DOWNLOAD_PAGE = "https://pan.baidu.com/disk/base/semdownload"
TIMEOUT = 30

VERSION_VER_RE = re.compile(r"window\.__V20_VER__\s*=\s*['\"](.+?)['\"]")


def _normalize_version(raw: str) -> str:
    """``4/24/2026, 2:55:02 PM`` → ``2026-04-24``；解析失败时原样返回。"""
    raw = raw.strip()
    for fmt in ("%m/%d/%Y, %I:%M:%S %p", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not platforms:
        raise FetchError("baidunetdisk: platforms 不能为空")

    assets: list[AssetInfo] = []
    version: str | None = None

    try:
        resp = get(
            DOWNLOAD_PAGE,
            timeout=TIMEOUT,
            headers=browser_headers(),
        )
        resp.raise_for_status()
        m = VERSION_VER_RE.search(resp.text)
        if m:
            version = _normalize_version(m.group(1))
    except requests.RequestException as exc:
        raise FetchError(f"baidunetdisk: 页面请求失败：{exc}") from exc

    for spec in platforms:
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=spec["download_url"],
                link_kind=spec.get("link_kind"),
            )
        )

    return FetchResult(
        id="baidunetdisk",
        name="百度网盘",
        version=version or "latest",
        source="百度网盘下载页（SPA，仅能取页面更新日期）",
        version_kind=VERSION_KIND_PAGE_DATE,
        version_source=VERSION_SOURCE_BAIDU_PAGE_TIMESTAMP,
        homepage="https://pan.baidu.com/",
        notes_url="https://pan.baidu.com/disk/base/semdownload",
        assets=assets,
    )
