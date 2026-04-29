"""Ubuntu official releases index fetcher."""

from __future__ import annotations

import re
from fnmatch import fnmatch
from typing import Any
from urllib.parse import urljoin

from ..link_utils import LINK_KIND_DIRECT
from ..net import get
from .base import VERSION_KIND_RELEASE, AssetInfo, FetchError, FetchResult

RELEASES_URL = "https://releases.ubuntu.com/"
VERSION_SOURCE = "Ubuntu releases index"
TIMEOUT = 30

RELEASE_HREF_RE = re.compile(r'href="(?P<version>\d{2}\.\d{2}(?:\.\d)?)/"')
FILE_HREF_RE = re.compile(r'href="(?P<filename>[^"]+)"')


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _latest_release_version(html: str) -> str:
    versions = sorted(
        {match.group("version") for match in RELEASE_HREF_RE.finditer(html)},
        key=_version_key,
    )
    if not versions:
        raise FetchError("ubuntu: no release directories found")
    return versions[-1]


def _release_files(html: str) -> list[str]:
    return [match.group("filename") for match in FILE_HREF_RE.finditer(html)]


def _find_file(files: list[str], pattern: str) -> str:
    matches = [filename for filename in files if fnmatch(filename, pattern)]
    if not matches:
        raise FetchError(f"ubuntu: no release file matched {pattern}")
    return sorted(matches)[-1]


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not platforms:
        raise FetchError("ubuntu: platforms must be a non-empty list")

    index_response = get(RELEASES_URL, timeout=TIMEOUT)
    index_response.raise_for_status()
    version = _latest_release_version(index_response.text)

    release_url = urljoin(RELEASES_URL, f"{version}/")
    release_response = get(release_url, timeout=TIMEOUT)
    release_response.raise_for_status()
    files = _release_files(release_response.text)

    assets: list[AssetInfo] = []
    for spec in platforms:
        pattern = spec["pattern"].format(version=version)
        filename = _find_file(files, pattern)
        assets.append(
            AssetInfo(
                platform=spec["platform"],
                url=urljoin(release_url, filename),
                link_kind=spec.get("link_kind", LINK_KIND_DIRECT),
                filename=filename,
            )
        )

    return FetchResult(
        id="",
        name="Ubuntu",
        version=version,
        source="Ubuntu official releases index",
        version_kind=VERSION_KIND_RELEASE,
        version_source=VERSION_SOURCE,
        homepage="https://ubuntu.com/download",
        notes_url=release_url,
        assets=assets,
    )
