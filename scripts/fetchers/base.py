"""Fetcher 公共数据结构。

每个 fetcher 都应返回一个 FetchResult，含若干 AssetInfo。
JSON 序列化由 to_dict / from_dict 负责，避免依赖 pydantic 等额外库。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AssetInfo:
    platform: str  # 例：win-x64 / mac-arm64 / mac-x64
    url: str  # 直接下载链接
    filename: str | None = None  # 原始文件名（GitHub Release 才有）
    size: int | None = None  # 字节
    sha256: str | None = None


@dataclass
class FetchResult:
    id: str
    name: str
    version: str
    source: str  # 数据来源描述，便于排错
    version_kind: str = "release_version"
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
