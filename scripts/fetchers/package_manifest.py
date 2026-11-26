"""从 WinGet / Homebrew / Scoop 的受信元数据刷新版本与下载资产，不执行清单脚本。"""

from __future__ import annotations

import io
import logging
import re
import sqlite3
import tempfile
import threading
import zipfile
from typing import Any

import requests
import yaml

from app_core.downloads import is_http_url
from scripts.net import get, get_json, github_headers
from .base import AssetInfo, FetchError, FetchResult
from .linux_store import LINUX_STORE_PROVIDERS, fetch_linux_source

API = "https://api.github.com/repos"
WINGET_RAW_BASE = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master"
WINGET_INDEX_URL = "https://cdn.winget.microsoft.com/cache/source2.msix"

_PACKAGE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*(?:/[A-Za-z0-9_.+-]+)?")
_ORIGINAL_GET = get
_ORIGINAL_GET_JSON = get_json
_WINGET_INDEX_LOCK = threading.Lock()
_WINGET_INDEX_CACHE: dict[str, str] | None = None

logger = logging.getLogger(__name__)


def parse_winget_index_msix(content: bytes) -> dict[str, str]:
    """从微软官方 WinGet source2.msix（ZIP + SQLite）解析包最新版本号映射。"""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        db_bytes = zf.read("Public/index.db")
    with tempfile.NamedTemporaryFile(suffix=".db") as tf:
        tf.write(db_bytes)
        tf.flush()
        conn = sqlite3.connect(tf.name)
        try:
            rows = conn.execute(
                "SELECT id, latest_version FROM packages WHERE latest_version IS NOT NULL"
            ).fetchall()
        finally:
            conn.close()
    return {str(pkg_id): str(ver) for pkg_id, ver in rows if pkg_id and ver}


def _winget_index_version(package: str) -> str | None:
    """进程内单例缓存官方 WinGet v2 索引；下载或解析失败时返回 None 回退 GitHub API。"""
    global _WINGET_INDEX_CACHE
    with _WINGET_INDEX_LOCK:
        if _WINGET_INDEX_CACHE is None:
            try:
                resp = get(WINGET_INDEX_URL, timeout=30, retries=2)
                try:
                    resp.raise_for_status()
                    _WINGET_INDEX_CACHE = parse_winget_index_msix(resp.content)
                finally:
                    resp.close()
            except Exception as exc:
                logger.warning("WinGet v2 index unavailable, falling back: %s", exc)
                _WINGET_INDEX_CACHE = {}
        return _WINGET_INDEX_CACHE.get(package)


_DEFAULT_WINGET_INDEX_VERSION = _winget_index_version


def select_winget_installer(
    data: dict,
    architecture: str,
    *,
    installer_locale: str | None = None,
    installer_type: str | None = None,
) -> dict:
    """同架构优先正式安装器和用户范围；支持语言/类型过滤；同优先级存在不同文件则人工消歧。"""
    types = [
        "wix",
        "msi",
        "inno",
        "nullsoft",
        "exe",
        "burn",
        "msix",
        "appx",
        "zip",
        "portable",
    ]
    matches = [
        item
        for item in data.get("Installers", [])
        if item.get("Architecture", data.get("Architecture")) == architecture
        and is_http_url(item.get("InstallerUrl", data.get("InstallerUrl")))
    ]
    if installer_type:
        want_type = installer_type.casefold()
        typed = [
            item
            for item in matches
            if str(
                item.get("InstallerType", data.get("InstallerType")) or ""
            ).casefold()
            == want_type
        ]
        if typed:
            matches = typed
    if installer_locale:
        want_locale = installer_locale.casefold()
        localized = [
            item
            for item in matches
            if str(
                item.get("InstallerLocale", data.get("InstallerLocale")) or ""
            ).casefold()
            == want_locale
        ]
        if localized:
            matches = localized
        else:
            neutral = [
                item
                for item in matches
                if not item.get("InstallerLocale", data.get("InstallerLocale"))
            ]
            if neutral:
                matches = neutral
    if not matches:
        raise FetchError("WinGet platform installer is missing")

    def rank(item: dict) -> tuple[int, int]:
        kind = item.get("InstallerType", data.get("InstallerType"))
        scope = item.get("Scope", data.get("Scope"))
        return (
            types.index(kind) if kind in types else len(types),
            {"user": 0, "machine": 1}.get(scope or "", 2),
        )

    best = min(map(rank, matches))
    chosen = {
        (
            item.get("InstallerUrl", data.get("InstallerUrl")),
            item.get("InstallerSha256", data.get("InstallerSha256")),
        ): item
        for item in matches
        if rank(item) == best
    }
    if len(chosen) != 1:
        raise FetchError("WinGet platform installer is ambiguous")
    return next(iter(chosen.values()))


def _read_url(value: Any) -> str:
    if not is_http_url(value) or any(token in value for token in ("$", "#{", "{{")):
        raise FetchError("manifest contains an unsupported download URL")
    return str(value)


def _asset(
    platform: str, url: Any, sha: Any = None, *, version: str | None = None
) -> AssetInfo:
    checksum = str(sha or "")
    return AssetInfo(
        platform=platform,
        url=_read_url(url),
        link_kind="direct",
        sha256=checksum if re.fullmatch(r"[a-fA-F0-9]{64}", checksum) else None,
        version=version,
    )


def _contents(repo: str, path: str) -> list[dict]:
    data = get_json(
        f"{API}/{repo}/contents/{path}", headers=github_headers(), timeout=30
    )
    if not isinstance(data, list):
        raise FetchError("manifest directory response is not a list")
    return data


_DEFAULT_CONTENTS = _contents


def _load_winget_yaml(url: str, package: str) -> dict:
    response = get(_read_url(url), timeout=30)
    try:
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        data = yaml.safe_load(response.text)
    finally:
        response.close()
    if not isinstance(data, dict) or data.get("PackageIdentifier") != package:
        raise FetchError("WinGet package identity mismatch")
    return data


def _winget_from_index(package: str) -> dict | None:
    version = _winget_index_version(package)
    if not version:
        return None
    parts = package.split(".")
    base = (
        f"{WINGET_RAW_BASE}/manifests/{parts[0][0].lower()}/"
        + "/".join(parts)
        + f"/{version}/{package}"
    )
    for suffix in (".installer.yaml", ".yaml"):
        try:
            return _load_winget_yaml(base + suffix, package)
        except requests.HTTPError as exc:
            if getattr(exc.response, "status_code", None) == 404:
                continue
            return None
        except Exception:
            return None
    return None


def _winget(package: str) -> dict:
    index_overridden = _winget_index_version is not _DEFAULT_WINGET_INDEX_VERSION
    legacy_mocked = (
        _contents is not _DEFAULT_CONTENTS
        or get_json is not _ORIGINAL_GET_JSON
        or get is not _ORIGINAL_GET
    )
    if index_overridden or not legacy_mocked:
        indexed = _winget_from_index(package)
        if indexed is not None:
            return indexed

    parts = package.split(".")
    path = f"manifests/{parts[0][0].lower()}/" + "/".join(parts)
    versions = [
        item
        for item in _contents("microsoft/winget-pkgs", path)
        if item.get("type") == "dir"
    ]
    if not versions:
        raise FetchError("WinGet package has no version directories")

    def version_key(item: dict) -> tuple:
        return tuple(
            (1, int(v)) if v.isdigit() else (0, v.casefold())
            for v in re.split(r"(\d+)", item["name"])
        )

    latest = max(versions, key=version_key)
    files = _contents("microsoft/winget-pkgs", latest["path"])
    manifests = [
        item for item in files if item.get("name", "").endswith(".installer.yaml")
    ]
    if not manifests:
        manifests = [item for item in files if item.get("name") == package + ".yaml"]
    if len(manifests) != 1:
        raise FetchError("WinGet installer manifest is missing or ambiguous")
    return _load_winget_yaml(manifests[0]["download_url"], package)


def _validate_identifier(package: str) -> None:
    if (
        not isinstance(package, str)
        or not _PACKAGE_ID_RE.fullmatch(package)
        or ".." in package
    ):
        raise FetchError("invalid package manifest identifier")


def _fetch_single(
    spec: dict[str, Any], *, include_asset_version: bool = False
) -> tuple[str, str, str, str | None, list[AssetInfo]]:
    provider, package = spec["provider"], spec["package"]
    if provider in LINUX_STORE_PROVIDERS:
        return fetch_linux_source(spec, include_asset_version=include_asset_version)
    _validate_identifier(package)
    platforms = [item["platform"] for item in spec["platforms"]]
    assets: list[AssetInfo] = []
    if provider == "brew":
        if "/" in package:
            raise FetchError("invalid Homebrew cask token")
        data = get_json(f"https://formulae.brew.sh/api/cask/{package}.json", timeout=30)
        if data.get("token") != package or data.get("disabled"):
            raise FetchError("Homebrew cask identity mismatch or disabled")
        version = str(data["version"])
        homepage = data.get("homepage")
        for platform in platforms:
            if platform == "mac":
                chosen = data
            elif (
                platform == "mac-universal"
                and "universal" in data.get("url", "").lower()
            ):
                chosen = data
            elif platform in {"mac-arm64", "mac-x64"}:
                arch = "arm64" if platform.endswith("arm64") else "x86_64"
                tokens = (
                    ("arm64", "aarch64")
                    if arch == "arm64"
                    else ("x86_64", "amd64", "intel", "x64")
                )
                default_url = data.get("url", "").lower()
                if any(t in default_url for t in tokens) or "universal" in default_url:
                    chosen = data
                else:
                    variations = {
                        v["url"]: v
                        for key, v in data.get("variations", {}).items()
                        if not key.endswith("_linux")
                        and v.get("url")
                        and str(v.get("version", version)) == version
                        and (
                            key.startswith(arch)
                            or any(t in v["url"].lower() for t in tokens)
                        )
                    }
                    if len(variations) != 1:
                        raise FetchError(
                            "Homebrew architecture is not established by metadata at the current version"
                        )
                    chosen = next(iter(variations.values()))
            else:
                raise FetchError(
                    "Homebrew supports mac platforms only; universal must be explicitly verified"
                )
            assets.append(
                _asset(
                    platform,
                    chosen.get("url", data.get("url")),
                    chosen.get("sha256", data.get("sha256")),
                    version=version if include_asset_version else None,
                )
            )
    elif provider == "scoop":
        parts = package.split("/", 1)
        if len(parts) != 2 or parts[0].lower() not in {"main", "extras"}:
            raise FetchError("Scoop identifier must be main/name or extras/name")
        bucket, token = parts
        data = get_json(
            f"https://raw.githubusercontent.com/ScoopInstaller/{bucket.title()}/master/bucket/{token}.json",
            timeout=30,
        )
        version, homepage = str(data["version"]), data.get("homepage")
        for platform in platforms:
            requested_arch = {
                "win-x64": "64bit",
                "win-x86": "32bit",
                "win-arm64": "arm64",
                "win": "neutral",
            }.get(platform)
            if requested_arch is None:
                raise FetchError("unsupported Scoop platform")
            chosen = data.get("architecture", {}).get(requested_arch)
            if chosen is None:
                if data.get("architecture"):
                    raise FetchError("Scoop manifest has no requested architecture")
                chosen = data
            url = chosen.get("url")
            if isinstance(url, list):
                if len(url) != 1:
                    raise FetchError(
                        "Scoop multi-file installers require manual mapping"
                    )
                url = url[0]
            assets.append(
                _asset(
                    platform,
                    url,
                    chosen.get("hash"),
                    version=version if include_asset_version else None,
                )
            )
    elif provider == "winget":
        if "/" in package or "." not in package:
            raise FetchError("invalid WinGet identifier")
        data = _winget(package)
        version, homepage = str(data["PackageVersion"]), None
        installer_locale = spec.get("installer_locale")
        installer_type = spec.get("installer_type")
        for platform in platforms:
            requested_arch = {
                "win-x64": "x64",
                "win-x86": "x86",
                "win-arm64": "arm64",
                "win": "neutral",
            }.get(platform)
            if requested_arch is None:
                raise FetchError("unsupported WinGet platform")
            installer = select_winget_installer(
                data,
                requested_arch,
                installer_locale=installer_locale,
                installer_type=installer_type,
            )
            assets.append(
                _asset(
                    platform,
                    installer.get("InstallerUrl", data.get("InstallerUrl")),
                    installer.get("InstallerSha256", data.get("InstallerSha256")),
                    version=version if include_asset_version else None,
                )
            )
    else:
        raise FetchError("unknown manifest provider")

    if not assets or not version:
        raise FetchError("manifest has no release version or assets")
    return (
        version,
        f"{provider} manifest: {package}",
        f"{provider} package manifest version",
        homepage,
        assets,
    )


def fetch(args: dict[str, Any]) -> FetchResult:
    sources = args.get("sources")
    if sources is None:
        version, source_label, version_source_label, homepage, assets = _fetch_single(
            args
        )
        name = str(args["package"])
    else:
        if not isinstance(sources, list) or not sources:
            raise FetchError("package_manifest: sources must be a non-empty list")
        multi = len(sources) > 1
        versions: list[str] = []
        source_labels: list[str] = []
        version_sources: list[str] = []
        assets = []
        seen_platforms: set[str] = set()
        homepage = None
        for spec in sources:
            ver, src_lbl, ver_src_lbl, src_hp, src_assets = _fetch_single(
                spec, include_asset_version=multi
            )
            for asset in src_assets:
                if asset.platform in seen_platforms:
                    raise FetchError(
                        f"package_manifest: duplicate platform {asset.platform}"
                    )
                seen_platforms.add(asset.platform)
                assets.append(asset)
            versions.append(ver)
            source_labels.append(src_lbl)
            version_sources.append(ver_src_lbl)
            if not homepage and src_hp:
                homepage = src_hp
        version = versions[0]
        source_label = " / ".join(dict.fromkeys(source_labels))
        version_source_label = " / ".join(dict.fromkeys(version_sources))
        name = str(sources[0]["package"])

    return FetchResult(
        id="",
        name=name,
        version=version,
        source=source_label,
        version_source=version_source_label,
        homepage=homepage,
        assets=assets,
    )
