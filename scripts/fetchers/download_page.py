"""Generic official download-page fetcher.

Use this for popular apps whose official download page always points users to
the latest build, but where no stable public version API is available.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..link_utils import LINK_KIND_LANDING_PAGE
from .base import (
    VERSION_KIND_SYNC_DATE,
    VERSION_SOURCE_UTC_SYNC_DATE,
    AssetInfo,
    FetchError,
    FetchResult,
)

DEFAULT_SOURCE = "Official download page; no public version API"


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not isinstance(platforms, list) or not platforms:
        raise FetchError("download_page: platforms must be a non-empty list")

    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    assets: list[AssetInfo] = []
    for spec in platforms:
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=spec["download_url"],
                link_kind=spec.get("link_kind", LINK_KIND_LANDING_PAGE),
            )
        )

    return FetchResult(
        id="",
        name=args.get("name", ""),
        version=today,
        source=args.get("source", DEFAULT_SOURCE),
        version_kind=VERSION_KIND_SYNC_DATE,
        version_source=VERSION_SOURCE_UTC_SYNC_DATE,
        homepage=args.get("homepage"),
        notes_url=args.get("notes_url") or args.get("homepage"),
        assets=assets,
    )
