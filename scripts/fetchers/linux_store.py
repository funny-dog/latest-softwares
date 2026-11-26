"""Linux 商店元数据抓取器（Flathub AppStream v2 + Snapcraft v2）。

既可作为独立 fetcher（`linux_store`）运行，也提供 `fetch_linux_source` 供
`package_manifest` 按 provider（`flathub` / `snapcraft`）复用。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app_core.downloads import is_http_url
from ..link_utils import LINK_KIND_DIRECT, LINK_KIND_LANDING_PAGE
from ..net import get_json
from .base import AssetInfo, FetchError, FetchResult

FLATHUB_API_BASE = "https://flathub.org/api/v2/appstream"
FLATHUB_FLATPAKREF_BASE = "https://dl.flathub.org/repo/appstream"
FLATHUB_PAGE_BASE = "https://flathub.org/en/apps"

SNAPCRAFT_API_BASE = "https://api.snapcraft.io/v2/snaps/info"
SNAPCRAFT_PAGE_BASE = "https://snapcraft.io"

LINUX_STORE_PROVIDERS = frozenset({"flathub", "snapcraft"})
LINUX_PLATFORMS = frozenset({"linux", "linux-x64", "linux-arm64"})
_SNAP_ARCH_MAP = {
    "linux": "amd64",
    "linux-x64": "amd64",
    "linux-arm64": "arm64",
}

_FLATHUB_ID_RE = re.compile(r"^[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+$")
_SNAP_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
TIMEOUT = 30


def _validate_flathub_id(package: str) -> None:
    if (
        not isinstance(package, str)
        or ".." in package
        or not _FLATHUB_ID_RE.fullmatch(package)
    ):
        raise FetchError("invalid Flathub app id")


def _validate_snap_id(package: str) -> None:
    if not isinstance(package, str) or not _SNAP_ID_RE.fullmatch(package):
        raise FetchError("invalid Snapcraft package name")


def _platform_names(spec: dict[str, Any]) -> list[str]:
    platforms = spec.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        raise FetchError("linux_store: platforms must be a non-empty list")
    names: list[str] = []
    for item in platforms:
        if not isinstance(item, dict) or not isinstance(item.get("platform"), str):
            raise FetchError("linux_store: invalid platform entry")
        names.append(item["platform"])
    return names


def _parse_flathub_timestamp(release: dict[str, Any]) -> str | None:
    ts = release.get("timestamp")
    if ts is not None and str(ts).isdigit():
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(
            timespec="seconds"
        )
    date_val = release.get("date")
    return str(date_val) if isinstance(date_val, str) and date_val else None


def _pick_flathub_release(data: dict[str, Any]) -> dict[str, Any]:
    releases = [
        item
        for item in (data.get("releases") or [])
        if isinstance(item, dict) and item.get("version")
    ]
    if not releases:
        raise FetchError("Flathub appstream has no release version")
    stable = [item for item in releases if item.get("type") == "stable"]
    return stable[0] if stable else releases[0]


def fetch_flathub(
    package: str,
    platforms: list[str],
    *,
    link_kind: str | None = None,
    include_asset_version: bool = False,
) -> tuple[str, str, str, str | None, list[AssetInfo], str | None, str | None]:
    """抓取 Flathub AppStream 元数据并返回标准化元信息与资产列表。"""
    _validate_flathub_id(package)
    for platform in platforms:
        if platform not in LINUX_PLATFORMS:
            raise FetchError(f"unsupported Flathub platform: {platform}")

    data = get_json(f"{FLATHUB_API_BASE}/{package}", timeout=TIMEOUT)
    if not isinstance(data, dict):
        raise FetchError("Flathub appstream response is not a JSON object")
    if data.get("id") and data.get("id") != package:
        raise FetchError("Flathub app identity mismatch")
    if data.get("is_eol"):
        raise FetchError(f"Flathub app {package} is end-of-life")

    release = _pick_flathub_release(data)
    version = str(release["version"]).strip()
    released_at = _parse_flathub_timestamp(release)
    raw_urls = data.get("urls")
    urls: dict[str, Any] = raw_urls if isinstance(raw_urls, dict) else {}
    page_url = f"{FLATHUB_PAGE_BASE}/{package}"
    homepage = urls.get("homepage") or page_url
    notes_url = release.get("url") or page_url

    kind = link_kind or LINK_KIND_DIRECT
    if kind == LINK_KIND_LANDING_PAGE:
        asset_url = page_url
        filename = None
    elif kind == LINK_KIND_DIRECT:
        asset_url = f"{FLATHUB_FLATPAKREF_BASE}/{package}.flatpakref"
        filename = f"{package}.flatpakref"
    else:
        raise FetchError(f"unsupported Flathub link_kind: {kind}")

    if not is_http_url(asset_url):
        raise FetchError("Flathub produced invalid asset URL")

    assets = [
        AssetInfo(
            platform=platform,
            url=asset_url,
            link_kind=kind,
            filename=filename,
            version=version if include_asset_version else None,
        )
        for platform in platforms
    ]
    return (
        version,
        f"flathub appstream: {package}",
        "Flathub AppStream v2 release",
        str(homepage) if homepage else None,
        assets,
        released_at,
        str(notes_url) if notes_url else None,
    )


def _select_snap_channel(
    channel_map: list[Any],
    *,
    arch: str,
    risk: str,
    track: str | None,
    default_track: str,
) -> dict[str, Any]:
    entries = [
        item
        for item in channel_map
        if isinstance(item, dict) and isinstance(item.get("channel"), dict)
    ]
    target_track = track or default_track
    matches = [
        item
        for item in entries
        if item["channel"].get("architecture") == arch
        and item["channel"].get("risk") == risk
        and item["channel"].get("track") == target_track
    ]
    if not matches and track is None:
        matches = [
            item
            for item in entries
            if item["channel"].get("architecture") == arch
            and item["channel"].get("risk") == risk
        ]
    if not matches:
        raise FetchError(
            f"Snapcraft package has no {target_track}/{risk} release for {arch}"
        )
    return matches[0]


def fetch_snapcraft(
    package: str,
    platforms: list[str],
    *,
    channel: str = "stable",
    track: str | None = None,
    link_kind: str | None = None,
    include_asset_version: bool = False,
) -> tuple[str, str, str, str | None, list[AssetInfo], str | None, str | None]:
    """抓取 Snapcraft v2 商店元数据并返回标准化元信息与资产列表。"""
    _validate_snap_id(package)
    for platform in platforms:
        if platform not in _SNAP_ARCH_MAP:
            raise FetchError(f"unsupported Snapcraft platform: {platform}")

    data = get_json(
        f"{SNAPCRAFT_API_BASE}/{package}",
        headers={"Snap-Device-Series": "16"},
        timeout=TIMEOUT,
    )
    if not isinstance(data, dict):
        raise FetchError("Snapcraft response is not a JSON object")
    if data.get("name") and data.get("name") != package:
        raise FetchError("Snapcraft package identity mismatch")

    channel_map = data.get("channel-map")
    if not isinstance(channel_map, list) or not channel_map:
        raise FetchError("Snapcraft package has empty channel-map")

    default_track = str(data.get("default-track") or "latest")
    raw_snap = data.get("snap")
    snap_meta: dict[str, Any] = raw_snap if isinstance(raw_snap, dict) else {}
    page_url = f"{SNAPCRAFT_PAGE_BASE}/{package}"
    homepage = snap_meta.get("website") or page_url
    kind = link_kind or LINK_KIND_LANDING_PAGE
    if kind not in {LINK_KIND_DIRECT, LINK_KIND_LANDING_PAGE}:
        raise FetchError(f"unsupported Snapcraft link_kind: {kind}")

    assets: list[AssetInfo] = []
    versions: list[str] = []
    released_at: str | None = None
    for platform in platforms:
        arch = _SNAP_ARCH_MAP[platform]
        chosen = _select_snap_channel(
            channel_map,
            arch=arch,
            risk=channel,
            track=track,
            default_track=default_track,
        )
        ver = str(chosen.get("version") or "").strip()
        if not ver:
            raise FetchError(f"Snapcraft {package} missing version for {arch}")
        versions.append(ver)
        if released_at is None:
            raw_rel = chosen["channel"].get("released-at")
            if isinstance(raw_rel, str) and raw_rel:
                released_at = raw_rel

        size: int | None = None
        if kind == LINK_KIND_DIRECT:
            raw_dl = chosen.get("download")
            dl: dict[str, Any] = raw_dl if isinstance(raw_dl, dict) else {}
            url = str(dl.get("url") or "")
            raw_size = dl.get("size")
            if isinstance(raw_size, int):
                size = raw_size
        else:
            url = page_url

        if not is_http_url(url):
            raise FetchError("Snapcraft produced invalid asset URL")

        assets.append(
            AssetInfo(
                platform=platform,
                url=url,
                link_kind=kind,
                size=size,
                version=ver if include_asset_version else None,
            )
        )

    if len(set(versions)) > 1 and not include_asset_version:
        for asset, ver in zip(assets, versions):
            asset.version = ver

    return (
        versions[0],
        f"snapcraft store: {package}",
        f"Snapcraft v2 {channel} channel",
        str(homepage) if homepage else None,
        assets,
        released_at,
        page_url,
    )


def fetch_linux_source(
    spec: dict[str, Any],
    *,
    include_asset_version: bool = False,
) -> tuple[str, str, str, str | None, list[AssetInfo]]:
    """兼容 package_manifest._fetch_single 的五元组返回接口。"""
    provider = spec.get("provider")
    package = spec.get("package")
    if not isinstance(package, str):
        raise FetchError("linux_store: package must be a string")
    platforms = _platform_names(spec)
    link_kind = spec.get("link_kind")
    if provider == "flathub":
        ver, src, ver_src, hp, assets, _, _ = fetch_flathub(
            package,
            platforms,
            link_kind=link_kind,
            include_asset_version=include_asset_version,
        )
        return ver, src, ver_src, hp, assets
    if provider == "snapcraft":
        ver, src, ver_src, hp, assets, _, _ = fetch_snapcraft(
            package,
            platforms,
            channel=str(spec.get("channel") or "stable"),
            track=spec.get("track"),
            link_kind=link_kind,
            include_asset_version=include_asset_version,
        )
        return ver, src, ver_src, hp, assets
    raise FetchError(f"unknown linux_store provider: {provider}")


def fetch(args: dict[str, Any]) -> FetchResult:
    """独立 fetcher 入口：支持单个 Flathub/Snapcraft 源或 sources 列表。"""
    sources = args.get("sources")
    if sources is None:
        provider = args.get("provider")
        package = args.get("package")
        if not isinstance(package, str):
            raise FetchError("linux_store: package must be a string")
        platforms = _platform_names(args)
        link_kind = args.get("link_kind")
        if provider == "flathub":
            ver, src, ver_src, hp, assets, released_at, notes_url = fetch_flathub(
                package, platforms, link_kind=link_kind
            )
        elif provider == "snapcraft":
            ver, src, ver_src, hp, assets, released_at, notes_url = fetch_snapcraft(
                package,
                platforms,
                channel=str(args.get("channel") or "stable"),
                track=args.get("track"),
                link_kind=link_kind,
            )
        else:
            raise FetchError(f"unknown linux_store provider: {provider}")
        return FetchResult(
            id="",
            name=package,
            version=ver,
            source=src,
            version_source=ver_src,
            homepage=hp,
            released_at=released_at,
            notes_url=notes_url,
            assets=assets,
        )

    if not isinstance(sources, list) or not sources:
        raise FetchError("linux_store: sources must be a non-empty list")
    multi = len(sources) > 1
    versions: list[str] = []
    source_labels: list[str] = []
    version_sources: list[str] = []
    assets_out: list[AssetInfo] = []
    seen_platforms: set[str] = set()
    homepage: str | None = None
    for spec in sources:
        if not isinstance(spec, dict):
            raise FetchError("linux_store: source entry must be an object")
        ver, src_lbl, ver_src_lbl, src_hp, src_assets = fetch_linux_source(
            spec, include_asset_version=multi
        )
        for asset in src_assets:
            if asset.platform in seen_platforms:
                raise FetchError(f"linux_store: duplicate platform {asset.platform}")
            seen_platforms.add(asset.platform)
            assets_out.append(asset)
        versions.append(ver)
        source_labels.append(src_lbl)
        version_sources.append(ver_src_lbl)
        if not homepage and src_hp:
            homepage = src_hp
    return FetchResult(
        id="",
        name=str(sources[0]["package"]),
        version=versions[0],
        source=" / ".join(dict.fromkeys(source_labels)),
        version_source=" / ".join(dict.fromkeys(version_sources)),
        homepage=homepage,
        assets=assets_out,
    )
