"""微信 PC 客户端下载链接抓取器。

腾讯为微信 Windows/Mac 维护了固定的重定向下载 URL，始终指向最新版安装包。
版本号优先从下载链接的 Content-Disposition 头解析（最权威）；失败时回退到
带上下文锚点的页面正则；都失败再用当天日期。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import requests

from ..net import browser_headers, get, head
from .base import AssetInfo, FetchResult


HOMEPAGE = "https://weixin.qq.com/"
WIN_DOWNLOAD = "https://dldir1.qq.com/weixin/Windows/WeChatSetup.exe"
TIMEOUT = 30

# 主段 < 100、各段 < 10000、3-4 段 —— 过滤 "214.172.387.384" 这类乱码命中。
# \b 边界防止从 "214.172..." 中间切出 "14.172..."。
_VERSION_RE = re.compile(
    r"(?<!\d)(\d{1,2})\.(\d{1,4})\.(\d{1,4})(?:\.(\d{1,4}))?(?!\d)",
)
# 上下文锚点：仅用 WeChat / 微信 作为锚点 —— 避免 "version" 命中 sdk-version 等噪声。
_CONTEXT_RE = re.compile(
    r"(?:WeChat|微信)[^\n]{0,80}?"
    r"(?<!\d)(\d{1,2}\.\d{1,4}\.\d{1,4}(?:\.\d{1,4})?)(?!\d)",
)
# Content-Disposition: attachment; filename=WeChat-3.9.10.27.exe
_FILENAME_VERSION_RE = re.compile(
    r"(?<!\d)(\d{1,2}\.\d{1,4}\.\d{1,4}(?:\.\d{1,4})?)(?!\d)",
)

logger = logging.getLogger(__name__)


def _is_plausible(version: str) -> bool:
    """版本号合理性校验：主段 < 100，每段 < 10000，段数 3-4。"""
    parts = version.split(".")
    if not 3 <= len(parts) <= 4:
        return False
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return False
    if nums[0] >= 100:
        return False
    return all(n < 10000 for n in nums)


def _from_content_disposition(url: str) -> str | None:
    """尝试从下载链接的 Content-Disposition 解析版本号。"""
    try:
        resp = head(url, timeout=TIMEOUT, allow_redirects=True)
    except requests.RequestException as exc:
        logger.debug("wechat: HEAD %s failed: %s", url, exc)
        return None
    cd = resp.headers.get("Content-Disposition", "")
    m = _FILENAME_VERSION_RE.search(cd)
    if m and _is_plausible(m.group(1)):
        return m.group(1)
    return None


def _from_homepage_html() -> str | None:
    """从微信官网 HTML 抓版本，要求带上下文锚点 + 合理性校验。"""
    try:
        resp = get(HOMEPAGE, timeout=TIMEOUT, headers=browser_headers())
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.debug("wechat: GET %s failed: %s", HOMEPAGE, exc)
        return None
    # 1) 优先：上下文锚点版本
    for m in _CONTEXT_RE.finditer(resp.text):
        if _is_plausible(m.group(1)):
            return m.group(1)
    # 2) 兜底：全文扫，但仍需合理性校验过滤垃圾匹配
    for m in _VERSION_RE.finditer(resp.text):
        candidate = ".".join(g for g in m.groups() if g is not None)
        if _is_plausible(candidate):
            return candidate
    return None


def _resolve_version() -> str:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    version = _from_content_disposition(WIN_DOWNLOAD)
    if version:
        return version
    version = _from_homepage_html()
    if version:
        return version
    logger.warning("wechat: 版本解析全部失败，回退使用日期 %s", today)
    return today


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    version = _resolve_version()

    assets: list[AssetInfo] = []
    for spec in platforms:
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=spec["download_url"],
            )
        )

    if not assets:
        assets.append(AssetInfo(platform="win-x64", url=WIN_DOWNLOAD))

    return FetchResult(
        id="wechat",
        name="微信",
        version=version,
        source="微信官网",
        version_kind="release_version",
        version_source="Content-Disposition / official page; date fallback when unavailable",
        homepage=HOMEPAGE,
        notes_url=HOMEPAGE,
        assets=assets,
    )
