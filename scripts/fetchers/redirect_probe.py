"""有界 HTTP HEAD / 302 重定向探测抓取器。

适用于官方提供固定稳定下载入口（通过 302 Location 或 Content-Disposition
暴露带版本号文件名），但无公开版本 JSON API 的商业软件。
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

import requests

from app_core.downloads import is_http_url
from ..link_utils import LINK_KIND_DIRECT
from ..net import base_headers, browser_headers, get, head
from .base import VERSION_KIND_RELEASE, AssetInfo, FetchError, FetchResult

TIMEOUT = 15
DEFAULT_MAX_HOPS = 6
MAX_ALLOWED_HOPS = 10
DEFAULT_VERSION_REGEX = r"(?<!\d)(\d+(?:\.\d+){1,3})(?!\d)"
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_HEAD_FALLBACK_STATUSES = frozenset({403, 405, 406, 501})


def _is_public_http_url(url: str) -> bool:
    if not is_http_url(url):
        return False
    host = (urlsplit(url).hostname or "").lower()
    if host == "localhost" or host.endswith((".localhost", ".local")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True


def _disposition_filename(disposition: str) -> str | None:
    extended = re.search(
        r"filename\*\s*=\s*(?:([\w!#$%&+^`{}~-]+)'[\w-]*')([^;]+)", disposition, re.I
    )
    if extended:
        charset, encoded = extended.group(1), extended.group(2).strip().strip('"')
        try:
            return unquote(encoded, encoding=charset or "utf-8", errors="replace")
        except LookupError:
            return unquote(encoded, errors="replace")
    plain = re.search(r'filename\s*=\s*(?:"([^"]*)"|([^;]+))', disposition, re.I)
    if plain:
        return (
            plain.group(1) if plain.group(1) is not None else plain.group(2)
        ).strip()
    return None


def _extract_version(
    pattern: re.Pattern[str],
    candidates: list[str | None],
) -> str | None:
    for text in candidates:
        if not text:
            continue
        match = pattern.search(text)
        if not match:
            continue
        if "version" in pattern.groupindex:
            return match.group("version")
        if pattern.groups >= 1:
            return match.group(1)
        return match.group(0)
    return None


def _request_hop(
    url: str,
    *,
    method: str,
    user_agent: str,
) -> requests.Response:
    headers = browser_headers() if user_agent == "browser" else base_headers()
    if method == "get":
        get_headers = {**headers, "Range": "bytes=0-0"}
        return get(
            url,
            headers=get_headers,
            stream=True,
            allow_redirects=False,
            timeout=TIMEOUT,
            retries=1,
        )
    resp = head(
        url,
        headers=headers,
        allow_redirects=False,
        timeout=TIMEOUT,
        retries=1,
    )
    if resp.status_code in _HEAD_FALLBACK_STATUSES:
        resp.close()
        fallback_headers = (
            base_headers({"Range": "bytes=0-0"})
            if resp.status_code in {403, 406} and user_agent == "browser"
            else {**headers, "Range": "bytes=0-0"}
        )
        return get(
            url,
            headers=fallback_headers,
            stream=True,
            allow_redirects=False,
            timeout=TIMEOUT,
            retries=1,
        )
    return resp


def probe_redirect(
    start_url: str,
    *,
    method: str = "head",
    max_hops: int = DEFAULT_MAX_HOPS,
    user_agent: str = "browser",
) -> tuple[str, str, int | None]:
    """沿重定向链探测最终 URL、Content-Disposition 与 Content-Length。"""
    if not _is_public_http_url(start_url):
        raise FetchError(f"redirect_probe: invalid or non-public URL: {start_url}")
    if method not in {"head", "get"}:
        raise FetchError(f"redirect_probe: unsupported method {method!r}")
    if user_agent not in {"browser", "sync"}:
        raise FetchError(f"redirect_probe: unsupported user_agent {user_agent!r}")
    if max_hops < 1 or max_hops > MAX_ALLOWED_HOPS:
        raise FetchError(
            f"redirect_probe: max_hops must be between 1 and {MAX_ALLOWED_HOPS}"
        )

    current = start_url
    for _ in range(max_hops + 1):
        if not _is_public_http_url(current):
            raise FetchError(
                f"redirect_probe: redirect to non-public URL blocked: {current}"
            )
        resp = _request_hop(current, method=method, user_agent=user_agent)
        try:
            if resp.status_code in _REDIRECT_STATUSES:
                location = resp.headers.get("Location")
                if not location:
                    raise FetchError("redirect_probe: redirect without Location header")
                current = urljoin(current, location)
                continue
            if not 200 <= resp.status_code < 400:
                raise FetchError(
                    f"redirect_probe: HTTP {resp.status_code} at {current}"
                )
            disposition = resp.headers.get("Content-Disposition", "")
            raw_len = resp.headers.get("Content-Length", "").strip()
            size = int(raw_len) if raw_len.isdigit() else None
            return current, disposition, size
        finally:
            resp.close()

    raise FetchError(f"redirect_probe: exceeded max_hops ({max_hops})")


def fetch(args: dict[str, Any]) -> FetchResult:
    """通过有界 HTTP HEAD / 302 探测解析版本与下载链接。"""
    platforms = args.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        raise FetchError("redirect_probe: platforms must be a non-empty list")

    default_regex = str(args.get("version_regex") or DEFAULT_VERSION_REGEX)
    default_method = str(args.get("method") or "head")
    default_ua = str(args.get("user_agent") or "browser")
    default_use_final = bool(args.get("use_final_url", False))
    default_max_hops = args.get("max_hops", DEFAULT_MAX_HOPS)
    if isinstance(default_max_hops, bool) or not isinstance(default_max_hops, int):
        raise FetchError("redirect_probe: max_hops must be an integer")

    assets: list[AssetInfo] = []
    versions: list[str] = []

    for spec in platforms:
        if not isinstance(spec, dict):
            raise FetchError("redirect_probe: platform entry must be an object")
        platform = spec.get("platform")
        start_url = spec.get("url") or spec.get("download_url")
        if not isinstance(platform, str) or not platform.strip():
            raise FetchError("redirect_probe: missing platform")
        if not isinstance(start_url, str) or not start_url.strip():
            raise FetchError(f"redirect_probe: missing url for {platform}")

        regex_str = str(spec.get("version_regex") or default_regex)
        try:
            pattern = re.compile(regex_str)
        except re.error as exc:
            raise FetchError(
                f"redirect_probe: invalid version_regex {regex_str!r}: {exc}"
            ) from exc

        hop_limit = spec.get("max_hops", default_max_hops)
        if isinstance(hop_limit, bool) or not isinstance(hop_limit, int):
            raise FetchError("redirect_probe: max_hops must be an integer")

        final_url, disposition, size = probe_redirect(
            start_url,
            method=str(spec.get("method") or default_method),
            max_hops=hop_limit,
            user_agent=str(spec.get("user_agent") or default_ua),
        )
        disp_filename = _disposition_filename(disposition)
        url_filename = unquote(PurePosixPath(urlsplit(final_url).path).name)
        filename = disp_filename or url_filename or None

        version = _extract_version(
            pattern,
            [disp_filename, disposition, url_filename, final_url],
        )
        if not version:
            raise FetchError(
                f"redirect_probe: could not extract version for {platform} from {final_url}"
            )

        use_final = bool(spec.get("use_final_url", default_use_final))
        asset_url = final_url if use_final else start_url
        versions.append(version)
        assets.append(
            AssetInfo(
                platform=platform,
                url=asset_url,
                link_kind=spec.get("link_kind", LINK_KIND_DIRECT),
                filename=filename,
                size=size,
            )
        )

    if len(set(versions)) > 1:
        for asset, ver in zip(assets, versions):
            asset.version = ver

    return FetchResult(
        id="",
        name=str(args.get("name") or ""),
        version=versions[0],
        source="HTTP redirect/header probe",
        version_kind=VERSION_KIND_RELEASE,
        version_source="HTTP redirect URL / Content-Disposition header",
        homepage=args.get("homepage"),
        notes_url=args.get("notes_url") or args.get("homepage"),
        assets=assets,
    )
