"""Blender official release directory fetcher.

blender.org 主站对非浏览器请求统一返回 Cloudflare 挑战页（HTTP 403，
`cf-mitigated: challenge`），落地页无法被自动核验。官方真正存放安装包的
`download.blender.org` 是普通 Apache 目录索引，可直接列举：

    https://download.blender.org/release/            → Blender5.3/ 等版本目录
    https://download.blender.org/release/Blender5.3/ → blender-5.3.0-windows-x64.msi 等

因此这里按目录索引解析最新版本，产出各平台官方直链，既有真实版本号
（不再是 sync_date），也能通过链接校验。
"""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from typing import Any
from urllib.parse import urljoin

from ..link_utils import LINK_KIND_DIRECT
from ..net import browser_headers, get
from .base import VERSION_KIND_RELEASE, AssetInfo, FetchError, FetchResult

INDEX_URL = "https://download.blender.org/release/"
VERSION_SOURCE = "Blender official download directory index"
TIMEOUT = 30

# 版本目录形如 Blender5.3/；只认「主.次」这种发布系列目录。
SERIES_HREF_RE = re.compile(r'href="Blender(?P<major>\d+)\.(?P<minor>\d+)/"')
FILE_HREF_RE = re.compile(r'href="(?P<filename>[^"]+)"')
# 目录里的安装包形如 blender-5.3.0-windows-x64.msi
VERSION_IN_NAME_RE = re.compile(r"^blender-(?P<version>\d+\.\d+\.\d+)-")


def _latest_series(html: str) -> tuple[int, int]:
    series = {
        (int(match.group("major")), int(match.group("minor")))
        for match in SERIES_HREF_RE.finditer(html)
    }
    if not series:
        raise FetchError("blender: no release series directories found")
    return max(series)


def _release_files(html: str) -> list[str]:
    return [match.group("filename") for match in FILE_HREF_RE.finditer(html)]


def _latest_version(files: list[str]) -> str:
    """取目录内出现过的最高补丁版本，避免把旧补丁目录当最新。"""
    versions = {
        match.group("version")
        for filename in files
        if (match := VERSION_IN_NAME_RE.match(filename))
    }
    if not versions:
        raise FetchError("blender: no blender-<version>-* files in release directory")
    return max(versions, key=lambda value: tuple(int(p) for p in value.split(".")))


def fetch(args: dict[str, Any]) -> FetchResult:
    platforms = args.get("platforms", [])
    if not platforms:
        raise FetchError("blender: platforms must be a non-empty list")

    index_response = get(INDEX_URL, headers=browser_headers(), timeout=TIMEOUT)
    index_response.raise_for_status()
    major, minor = _latest_series(index_response.text)
    release_url = urljoin(INDEX_URL, f"Blender{major}.{minor}/")

    release_response = get(release_url, headers=browser_headers(), timeout=TIMEOUT)
    release_response.raise_for_status()
    files = _release_files(release_response.text)
    version = _latest_version(files)

    assets: list[AssetInfo] = []
    for spec in platforms:
        # pattern 用 fnmatch，{version} 替换为本次解析出的补丁版本号。
        pattern = spec["pattern"].format(version=version)
        matches = [filename for filename in files if fnmatchcase(filename, pattern)]
        if len(matches) > 1:
            raise FetchError(
                f"blender@{version}: {spec['platform']} pattern {pattern!r} "
                f"匹配多个文件，需收紧规则: {sorted(matches)}"
            )
        if not matches:
            raise FetchError(f"blender@{version}: no release file matched {pattern!r}")
        filename = matches[0]
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
        name="Blender",
        version=version,
        source="Blender official download directory",
        version_kind=VERSION_KIND_RELEASE,
        version_source=VERSION_SOURCE,
        homepage="https://www.blender.org/download/",
        # 主站的 release notes 页同样被 Cloudflare 挑战挡住，指向真正可达的发布目录。
        notes_url=release_url,
        assets=assets,
    )
