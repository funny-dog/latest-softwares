"""Mozilla Firefox official version and download URL fetcher."""

from __future__ import annotations

from typing import Any

from ..net import get_json
from .base import (
    VERSION_KIND_RELEASE,
    AssetInfo,
    FetchError,
    FetchResult,
)

VERSIONS_URL = "https://product-details.mozilla.org/1.0/firefox_versions.json"
DOWNLOAD_URL_TMPL = (
    "https://download.mozilla.org/?product={product}&os={os}&lang={lang}"
)
VERSION_SOURCE = "Mozilla product-details firefox_versions.json"
TIMEOUT = 30


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not platforms:
        raise FetchError("firefox: platforms must be a non-empty list")

    payload = get_json(VERSIONS_URL, timeout=TIMEOUT)
    version = payload.get("LATEST_FIREFOX_VERSION")
    if not version:
        raise FetchError("firefox: missing LATEST_FIREFOX_VERSION")

    lang = args.get("lang", "en-US")
    assets: list[AssetInfo] = []
    for spec in platforms:
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=DOWNLOAD_URL_TMPL.format(
                    product=spec.get("product", "firefox-latest-ssl"),
                    os=spec["os"],
                    lang=spec.get("lang", lang),
                ),
                link_kind=spec.get("link_kind"),
            )
        )

    return FetchResult(
        id="",
        name="Mozilla Firefox",
        version=version,
        source="Mozilla product-details API",
        version_kind=VERSION_KIND_RELEASE,
        version_source=VERSION_SOURCE,
        homepage="https://www.mozilla.org/firefox/new/",
        notes_url="https://www.mozilla.org/firefox/releases/",
        assets=assets,
    )
