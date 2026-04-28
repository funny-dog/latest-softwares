"""共享的"固定跳转页"fetcher 工厂。

适用于无公开版本 API、下载页为 SPA 或固定重定向链接的应用：
qq、yy、wegame、nvidia_app 等。版本号取当天日期（仅作为同步日期标记），
下载链接由 packages.yaml 透传。

返回的是普通的 fetcher 函数，注册表无需感知它来自工厂。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from ..link_utils import LINK_KIND_LANDING_PAGE
from .base import (
    VERSION_KIND_SYNC_DATE,
    VERSION_SOURCE_UTC_SYNC_DATE,
    AssetInfo,
    FetchResult,
)


def make_redirect_fetcher(
    *,
    id: str,
    name: str,
    homepage: str,
    download_page: str,
    default_platform: str = "win-x64",
    source: str = "手动同步（无 API）",
) -> Callable[[dict[str, Any]], FetchResult]:
    """构造一个"日期版本 + URL 透传"fetcher。

    Args:
        id: latest.json 中使用的稳定标识。
        name: 显示名。
        homepage: 应用主页（README 链接）。
        download_page: 下载页 URL，作为 notes_url 与缺省 asset url。
        default_platform: 当 args.platforms 为空时兜底的 platform 名。
        source: 数据来源描述（默认显示"无 API"）。
    """

    def fetch(args: dict[str, Any]) -> FetchResult:
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

        assets: list[AssetInfo] = [
            AssetInfo(
                platform=spec["platform"],
                url=spec.get("download_url") or download_page,
                link_kind=spec.get("link_kind", LINK_KIND_LANDING_PAGE),
            )
            for spec in args.get("platforms", [])
        ]
        if not assets:
            assets.append(
                AssetInfo(
                    platform=default_platform,
                    url=download_page,
                    link_kind=LINK_KIND_LANDING_PAGE,
                )
            )

        return FetchResult(
            id=id,
            name=name,
            version=today,
            source=source,
            version_kind=VERSION_KIND_SYNC_DATE,
            version_source=VERSION_SOURCE_UTC_SYNC_DATE,
            homepage=homepage,
            notes_url=download_page,
            assets=assets,
        )

    return fetch
