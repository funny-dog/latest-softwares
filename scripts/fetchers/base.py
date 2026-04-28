"""Fetcher 公共数据结构。

每个 fetcher 都应返回一个 FetchResult，含若干 AssetInfo。
JSON 序列化由 to_dict / from_dict 负责，避免依赖 pydantic 等额外库。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

VERSION_KIND_RELEASE = "release_version"
VERSION_KIND_RELEASE_LABEL = "release_label"
VERSION_KIND_BUILD_DATE = "build_date"
VERSION_KIND_PAGE_DATE = "page_date"
VERSION_KIND_SYNC_DATE = "sync_date"
VERSION_KINDS = {
    VERSION_KIND_RELEASE,
    VERSION_KIND_RELEASE_LABEL,
    VERSION_KIND_BUILD_DATE,
    VERSION_KIND_PAGE_DATE,
    VERSION_KIND_SYNC_DATE,
}

VERSION_SOURCE_GITHUB_TAG = "GitHub release tag"
VERSION_SOURCE_VSCODE_MANIFEST = "VSCode Build Manifest productVersion"
VERSION_SOURCE_GOOGLE_VERSION_HISTORY = "Google Version History API"
VERSION_SOURCE_VALVE_CLIENT_TIMESTAMP = "Valve Client Update API timestamp"
VERSION_SOURCE_FIDO_ISO_FILENAME = (
    "Fido ISO filename parsed from Microsoft download URL"
)
VERSION_SOURCE_BAIDU_PAGE_TIMESTAMP = "download page window.__V20_VER__ build timestamp"
VERSION_SOURCE_OFFICIAL_PAGE_HTML = "official download page HTML"
VERSION_SOURCE_WECHAT = (
    "Content-Disposition / official page; date fallback when unavailable"
)
VERSION_SOURCE_UTC_SYNC_DATE = "UTC sync date; no public version API"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AssetInfo:
    platform: str  # 例：win-x64 / mac-arm64 / mac-x64
    url: str  # 直接下载链接
    link_kind: str | None = None  # direct / landing_page；为空时由 URL 后缀推断
    filename: str | None = None  # 原始文件名（GitHub Release 才有）
    size: int | None = None  # 字节
    sha256: str | None = None


@dataclass
class FetchResult:
    id: str
    name: str
    version: str
    source: str  # 数据来源描述，便于排错
    version_kind: str = VERSION_KIND_RELEASE
    version_source: str | None = None
    category: str | None = None
    homepage: str | None = None
    released_at: str | None = None  # ISO8601 字符串
    notes_url: str | None = None  # 更新日志链接
    assets: list[AssetInfo] = field(default_factory=list)
    fetched_at: str = field(default_factory=_utc_now_iso)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data.get("version_source") is None:
            data["version_source"] = data["source"]
        if not data["warnings"]:
            data.pop("warnings")
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FetchResult":
        assets_data = data.pop("assets", []) or []
        result = cls(**data)
        result.assets = [AssetInfo(**a) for a in assets_data]
        return result


class FetchError(Exception):
    """Fetcher 失败时抛出，sync.py 会捕获并落入 stderr。"""
