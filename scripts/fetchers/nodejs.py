"""Node.js official release index fetcher."""

from __future__ import annotations

from typing import Any

from ..net import get_json
from .base import (
    VERSION_KIND_RELEASE,
    AssetInfo,
    FetchError,
    FetchResult,
)

INDEX_URL = "https://nodejs.org/dist/index.json"
DOWNLOAD_URL_TMPL = "https://nodejs.org/dist/{version}/{filename}"
VERSION_SOURCE = "Node.js official dist index.json"
TIMEOUT = 30


def _latest_lts_release(releases: list[dict]) -> dict:
    for release in releases:
        if release.get("lts"):
            return release
    raise FetchError("nodejs: no LTS release found in official index")


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not platforms:
        raise FetchError("nodejs: platforms must be a non-empty list")

    releases = get_json(INDEX_URL, timeout=TIMEOUT)
    if not isinstance(releases, list) or not releases:
        raise FetchError("nodejs: official index returned no releases")

    release = _latest_lts_release(releases)
    version = release["version"]
    files = set(release.get("files", []))

    assets: list[AssetInfo] = []
    for spec in platforms:
        file_key = spec["file_key"]
        if file_key not in files:
            raise FetchError(f"nodejs: {version} does not publish {file_key}")
        filename = spec["filename"].format(version=version)
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=DOWNLOAD_URL_TMPL.format(version=version, filename=filename),
                link_kind=spec.get("link_kind"),
            )
        )

    return FetchResult(
        id="",
        name="Node.js",
        version=version.removeprefix("v"),
        source="Node.js official dist index",
        version_kind=VERSION_KIND_RELEASE,
        version_source=VERSION_SOURCE,
        homepage="https://nodejs.org/",
        notes_url=f"https://nodejs.org/en/blog/release/{version}",
        assets=assets,
    )
