"""Fedora official release directory fetcher."""

from __future__ import annotations

import re
from fnmatch import fnmatch
from typing import Any
from urllib.parse import urljoin

from ..link_utils import LINK_KIND_DIRECT
from ..net import get
from .base import VERSION_KIND_RELEASE, AssetInfo, FetchError, FetchResult

RELEASES_URL = "https://dl.fedoraproject.org/pub/fedora/linux/releases/"
DEFAULT_EDITION_PATH = "Workstation/x86_64/iso"
VERSION_SOURCE = "Fedora official release directory"
TIMEOUT = 30

RELEASE_HREF_RE = re.compile(r'href="(?P<version>\d+)/"')
FILE_HREF_RE = re.compile(r'href="(?P<filename>[^"]+)"')


def _latest_release_version(html: str) -> str:
    versions = sorted(
        {int(match.group("version")) for match in RELEASE_HREF_RE.finditer(html)}
    )
    if not versions:
        raise FetchError("fedora: no release directories found")
    return str(versions[-1])


def _release_files(html: str) -> list[str]:
    return [match.group("filename") for match in FILE_HREF_RE.finditer(html)]


def _find_file(files: list[str], pattern: str) -> str:
    matches = [filename for filename in files if fnmatch(filename, pattern)]
    if not matches:
        raise FetchError(f"fedora: no release file matched {pattern}")
    return sorted(matches)[-1]


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not platforms:
        raise FetchError("fedora: platforms must be a non-empty list")

    index_response = get(RELEASES_URL, timeout=TIMEOUT)
    index_response.raise_for_status()
    version = _latest_release_version(index_response.text)

    edition_path = args.get("edition_path", DEFAULT_EDITION_PATH).strip("/")
    release_url = urljoin(RELEASES_URL, f"{version}/{edition_path}/")
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
        name="Fedora Workstation",
        version=version,
        source="Fedora official release directory",
        version_kind=VERSION_KIND_RELEASE,
        version_source=VERSION_SOURCE,
        homepage="https://fedoraproject.org/workstation/download/",
        notes_url="https://docs.fedoraproject.org/en-US/fedora/latest/release-notes/",
        assets=assets,
    )
