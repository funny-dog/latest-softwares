"""客户端自更新源抓取器（Electron latest*.yml / Sparkle appcast.xml / JSON update）。"""

from __future__ import annotations

import fnmatch
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlsplit

import yaml

from app_core.downloads import is_http_url
from ..link_utils import LINK_KIND_DIRECT
from ..net import get
from .base import VERSION_KIND_RELEASE, AssetInfo, FetchError, FetchResult

TIMEOUT = 30
SUPPORTED_FORMATS = frozenset({"electron", "sparkle", "json"})


def _natural_version_key(version: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part.casefold())
        for part in re.split(r"(\d+)", version)
        if part
    )


def _fetch_text(url: str) -> str:
    if not is_http_url(url):
        raise FetchError(f"updater_feed: invalid feed URL: {url}")
    response = get(url, timeout=TIMEOUT)
    try:
        response.raise_for_status()
        return response.text
    finally:
        response.close()


def _url_filename(url: str) -> str:
    return PurePosixPath(urlsplit(url).path).name


def _parse_electron_feed(
    feed_text: str,
    feed_url: str,
    *,
    pattern: str | None = None,
) -> tuple[str, str, int | None, str | None, str | None]:
    data = yaml.safe_load(feed_text)
    if not isinstance(data, dict):
        raise FetchError("updater_feed: Electron feed is not a YAML mapping")
    version = str(data.get("version") or "").strip()
    if not version:
        raise FetchError("updater_feed: Electron feed missing version")

    released_at = data.get("releaseDate")
    released_iso = (
        str(released_at).strip()
        if isinstance(released_at, str) and released_at.strip()
        else None
    )

    candidates: list[tuple[str, int | None, str | None]] = []
    seen_urls: set[str] = set()

    def add_candidate(
        raw_url: Any, size_val: Any = None, sha256_val: Any = None
    ) -> None:
        if not isinstance(raw_url, str) or not raw_url.strip():
            return
        resolved = urljoin(feed_url, raw_url.strip())
        if resolved in seen_urls:
            return
        seen_urls.add(resolved)
        size = size_val if isinstance(size_val, int) else None
        sha = (
            str(sha256_val)
            if isinstance(sha256_val, str)
            and re.fullmatch(r"[0-9a-fA-F]{64}", sha256_val)
            else None
        )
        candidates.append((resolved, size, sha))

    files = data.get("files")
    if isinstance(files, list):
        for item in files:
            if isinstance(item, dict):
                add_candidate(item.get("url"), item.get("size"), item.get("sha256"))
    add_candidate(data.get("path"))

    if not candidates:
        raise FetchError("updater_feed: Electron feed has no file path or files[]")

    if pattern:
        resolved_pattern = pattern.replace("{version}", version)
        matches = [
            cand
            for cand in candidates
            if fnmatch.fnmatchcase(_url_filename(cand[0]), resolved_pattern)
        ]
        if len(matches) > 1:
            raise FetchError(
                f"updater_feed: Electron pattern {resolved_pattern!r} matched multiple files"
            )
        if not matches:
            raise FetchError(
                f"updater_feed: Electron pattern {resolved_pattern!r} matched no files"
            )
        chosen_url, size, sha256 = matches[0]
    else:
        path_raw = data.get("path")
        if isinstance(path_raw, str) and path_raw.strip():
            target = urljoin(feed_url, path_raw.strip())
            chosen_url, size, sha256 = next(
                (cand for cand in candidates if cand[0] == target),
                (target, None, None),
            )
        elif len(candidates) == 1:
            chosen_url, size, sha256 = candidates[0]
        else:
            raise FetchError(
                "updater_feed: Electron feed has multiple files; specify pattern"
            )

    if not is_http_url(chosen_url):
        raise FetchError("updater_feed: Electron resolved asset URL is invalid")
    return version, chosen_url, size, sha256, released_iso


def _local_name(tag_or_attr: str) -> str:
    return tag_or_attr.split("}", 1)[-1] if "}" in tag_or_attr else tag_or_attr


def _attr_by_local(elem: ET.Element, name: str) -> str | None:
    for key, val in elem.attrib.items():
        if _local_name(key) == name and val.strip():
            return val.strip()
    return None


def _child_text_by_local(elem: ET.Element, name: str) -> str | None:
    for child in elem:
        if _local_name(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return None


def _parse_rfc2822_date(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _parse_sparkle_feed(
    feed_text: str,
    feed_url: str,
    *,
    pattern: str | None = None,
    os_filter: str | None = None,
) -> tuple[str, str, int | None, None, str | None]:
    try:
        root = ET.fromstring(feed_text)
    except (ET.ParseError, ValueError) as exc:
        raise FetchError(f"updater_feed: invalid Sparkle XML: {exc}") from exc

    entries: list[tuple[str, str, int | None, str | None]] = []
    for item in root.findall(".//item"):
        pub_date = _parse_rfc2822_date(_child_text_by_local(item, "pubDate"))
        item_short = _child_text_by_local(item, "shortVersionString")
        item_build = _child_text_by_local(item, "version")

        for enclosure in item.findall("enclosure"):
            raw_url = enclosure.attrib.get("url", "").strip()
            if not raw_url:
                continue
            enc_os = _attr_by_local(enclosure, "os")
            if os_filter and enc_os and enc_os.casefold() != os_filter.casefold():
                continue
            if os_filter and enc_os is None:
                continue

            version = (
                _attr_by_local(enclosure, "shortVersionString")
                or item_short
                or _attr_by_local(enclosure, "version")
                or item_build
            )
            if not version:
                continue

            resolved = urljoin(feed_url, raw_url)
            if not is_http_url(resolved):
                continue
            if pattern:
                resolved_pattern = pattern.replace("{version}", version)
                if not fnmatch.fnmatchcase(_url_filename(resolved), resolved_pattern):
                    continue

            raw_len = enclosure.attrib.get("length", "").strip()
            size = int(raw_len) if raw_len.isdigit() else None
            entries.append((version, resolved, size, pub_date))

    if not entries:
        raise FetchError("updater_feed: Sparkle appcast has no matching enclosure")

    best_version = max((entry[0] for entry in entries), key=_natural_version_key)
    top = [entry for entry in entries if entry[0] == best_version]
    distinct_urls = list(dict.fromkeys(entry[1] for entry in top))
    if len(distinct_urls) > 1:
        raise FetchError(
            "updater_feed: Sparkle appcast has multiple enclosures at latest version; specify pattern"
        )
    version, chosen_url, size, released_at = top[0]
    return version, chosen_url, size, None, released_at


def _parse_json_feed(
    feed_text: str,
    feed_url: str,
    *,
    url_key: str | None = None,
    version_key: str | None = None,
) -> tuple[str, str, int | None, str | None, str | None]:
    try:
        data = json.loads(feed_text)
    except ValueError as exc:
        raise FetchError(f"updater_feed: invalid JSON feed: {exc}") from exc
    if not isinstance(data, dict):
        raise FetchError("updater_feed: JSON feed is not an object")

    ver_keys = (version_key,) if version_key else ("version", "productVersion", "name")
    version = next(
        (str(data[k]).strip() for k in ver_keys if k in data and str(data[k]).strip()),
        "",
    )
    if not version:
        raise FetchError("updater_feed: JSON feed missing version")

    url_keys = (url_key,) if url_key else ("url", "downloadUrl")
    raw_url = next(
        (str(data[k]).strip() for k in url_keys if k in data and str(data[k]).strip()),
        "",
    )
    if not raw_url:
        raise FetchError("updater_feed: JSON feed missing download URL")

    chosen_url = urljoin(feed_url, raw_url)
    if not is_http_url(chosen_url):
        raise FetchError("updater_feed: JSON resolved asset URL is invalid")

    raw_sha = data.get("sha256hash") or data.get("sha256")
    sha256 = (
        str(raw_sha)
        if isinstance(raw_sha, str) and re.fullmatch(r"[0-9a-fA-F]{64}", raw_sha)
        else None
    )
    raw_size = data.get("size")
    size = raw_size if isinstance(raw_size, int) else None

    released_at: str | None = None
    ts = data.get("timestamp")
    if isinstance(ts, (int, float)) and not isinstance(ts, bool) and ts > 0:
        seconds = ts / 1000.0 if ts > 1e11 else float(ts)
        released_at = datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat(
            timespec="seconds"
        )
    elif isinstance(data.get("releaseDate"), str) and data["releaseDate"].strip():
        released_at = data["releaseDate"].strip()

    return version, chosen_url, size, sha256, released_at


def fetch(args: dict[str, Any]) -> FetchResult:
    """抓取 Electron latest*.yml 或 Sparkle appcast.xml 更新源。"""
    platforms = args.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        raise FetchError("updater_feed: platforms must be a non-empty list")

    default_format = args.get("format")
    feed_cache: dict[str, str] = {}
    assets: list[AssetInfo] = []
    versions: list[str] = []
    formats_used: list[str] = []
    released_at: str | None = None

    for spec in platforms:
        if not isinstance(spec, dict):
            raise FetchError("updater_feed: platform entry must be an object")
        platform = spec.get("platform")
        feed_url = spec.get("feed_url")
        fmt = spec.get("format") or default_format
        if not isinstance(platform, str) or not platform.strip():
            raise FetchError("updater_feed: missing platform")
        if not isinstance(feed_url, str) or not is_http_url(feed_url):
            raise FetchError(f"updater_feed: invalid feed_url for {platform}")
        if fmt not in SUPPORTED_FORMATS:
            raise FetchError(f"updater_feed: unsupported format {fmt!r}")

        if feed_url not in feed_cache:
            feed_cache[feed_url] = _fetch_text(feed_url)
        feed_text = feed_cache[feed_url]

        pattern = spec.get("pattern")
        if fmt == "electron":
            ver, asset_url, size, sha256, rel_at = _parse_electron_feed(
                feed_text,
                feed_url,
                pattern=str(pattern) if pattern else None,
            )
        elif fmt == "sparkle":
            ver, asset_url, size, sha256, rel_at = _parse_sparkle_feed(
                feed_text,
                feed_url,
                pattern=str(pattern) if pattern else None,
                os_filter=str(spec["os"]) if spec.get("os") else None,
            )
        else:
            ver, asset_url, size, sha256, rel_at = _parse_json_feed(
                feed_text,
                feed_url,
                url_key=str(spec.get("url_key") or args.get("url_key") or "") or None,
                version_key=str(
                    spec.get("version_key") or args.get("version_key") or ""
                )
                or None,
            )

        versions.append(ver)
        formats_used.append(str(fmt))
        if released_at is None and rel_at:
            released_at = rel_at

        assets.append(
            AssetInfo(
                platform=platform,
                url=asset_url,
                link_kind=spec.get("link_kind", LINK_KIND_DIRECT),
                filename=_url_filename(asset_url) or None,
                size=size,
                sha256=sha256,
            )
        )

    if len(set(versions)) > 1:
        for asset, ver in zip(assets, versions):
            asset.version = ver

    fmt_label = "/".join(dict.fromkeys(formats_used))
    return FetchResult(
        id="",
        name=str(args.get("name") or ""),
        version=versions[0],
        source=f"Self-update feed ({fmt_label})",
        version_kind=VERSION_KIND_RELEASE,
        version_source=f"Client self-update {fmt_label} feed",
        homepage=args.get("homepage"),
        released_at=released_at,
        notes_url=args.get("notes_url") or args.get("homepage"),
        assets=assets,
    )
