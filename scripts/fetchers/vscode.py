"""VSCode 官方多平台元数据抓取器。

端点：https://code.visualstudio.com/sha?build=stable
返回 JSON 列出**所有平台**的最新构建（一次请求拿全），每条含
url / productVersion / sha256hash / platform.os 等字段。

只需在 packages.yaml 里列出关心的 platform.os 名（如 "win32-x64-user"），
fetcher 自动从全量数据中筛选。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..net import get_json
from .base import AssetInfo, FetchError, FetchResult


API_URL = "https://code.visualstudio.com/sha?build=stable"
TIMEOUT = 30


def fetch(args: dict[str, Any]) -> FetchResult:
    builds = args.get("builds", [])
    if not builds:
        raise FetchError("vscode: builds 不能为空")

    products = get_json(API_URL, timeout=TIMEOUT).get("products", [])
    if not products:
        raise FetchError("vscode: API 返回空 products 数组")

    by_os = {p["platform"]["os"]: p for p in products if "platform" in p}

    assets: list[AssetInfo] = []
    version: str | None = None
    timestamp_ms: int | None = None

    for spec in builds:
        platform = spec["platform"]
        os_key = spec["build"]
        product = by_os.get(os_key)
        if not product:
            # 跳过不存在的 build；其它 build 仍可继续
            continue
        if version is None:
            version = product.get("productVersion")
            timestamp_ms = product.get("timestamp")
        assets.append(
            AssetInfo(
                platform=platform,
                url=product["url"],
                sha256=product.get("sha256hash"),
            )
        )

    if not assets:
        available = sorted(by_os.keys())
        raise FetchError(
            f"vscode: 配置的 builds 在 API 中都不存在。可用 os: {available}"
        )
    if not version:
        raise FetchError("vscode: 未能拿到 productVersion")

    released_at = None
    if timestamp_ms:
        released_at = datetime.fromtimestamp(
            timestamp_ms / 1000, tz=timezone.utc
        ).isoformat(timespec="seconds")

    notes_anchor = version.rsplit(".", 1)[0].replace(".", "_")  # "1.117.0" -> "1_117"
    return FetchResult(
        id="",
        name="Visual Studio Code",
        version=version,
        source="VSCode Build Manifest",
        homepage="https://code.visualstudio.com",
        released_at=released_at,
        notes_url=f"https://code.visualstudio.com/updates/v{notes_anchor}",
        assets=assets,
    )
