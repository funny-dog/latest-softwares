"""从 WinGet / Homebrew / Scoop 的受信元数据刷新版本与下载资产，不执行清单脚本。"""

from __future__ import annotations

import re
from typing import Any

import yaml

from app_core.downloads import is_http_url
from scripts.net import get, get_json, github_headers
from .base import AssetInfo, FetchError, FetchResult

API = "https://api.github.com/repos"


def select_winget_installer(data: dict, architecture: str) -> dict:
    """同架构优先正式安装器和用户范围；同优先级存在不同文件则人工消歧。"""
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


def _asset(platform: str, url: Any, sha: Any = None) -> AssetInfo:
    checksum = str(sha or "")
    return AssetInfo(
        platform=platform,
        url=_read_url(url),
        link_kind="direct",
        sha256=checksum if re.fullmatch(r"[a-fA-F0-9]{64}", checksum) else None,
    )


def _contents(repo: str, path: str) -> list[dict]:
    data = get_json(
        f"{API}/{repo}/contents/{path}", headers=github_headers(), timeout=30
    )
    if not isinstance(data, list):
        raise FetchError("manifest directory response is not a list")
    return data


def _winget(package: str) -> dict:
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
    response = get(_read_url(manifests[0]["download_url"]), timeout=30)
    try:
        data = yaml.safe_load(response.text)
    finally:
        response.close()
    if not isinstance(data, dict) or data.get("PackageIdentifier") != package:
        raise FetchError("WinGet package identity mismatch")
    return data


def fetch(args: dict[str, Any]) -> FetchResult:
    provider, package = args["provider"], args["package"]
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*(?:/[A-Za-z0-9_.+-]+)?", package)
        or ".." in package
    ):
        raise FetchError("invalid package manifest identifier")
    platforms = [item["platform"] for item in args["platforms"]]
    assets = []
    if provider == "brew":
        if "/" in package:
            raise FetchError("invalid Homebrew cask token")
        data = get_json(f"https://formulae.brew.sh/api/cask/{package}.json", timeout=30)
        if data.get("token") != package or data.get("disabled"):
            raise FetchError("Homebrew cask identity mismatch or disabled")
        version = data["version"]
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
                        and str(v.get("version", version)) == str(version)
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
        version, homepage = data["version"], data.get("homepage")
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
            assets.append(_asset(platform, url, chosen.get("hash")))
    elif provider == "winget":
        if "/" in package or "." not in package:
            raise FetchError("invalid WinGet identifier")
        data = _winget(package)
        version, homepage = data["PackageVersion"], None
        for platform in platforms:
            requested_arch = {
                "win-x64": "x64",
                "win-x86": "x86",
                "win-arm64": "arm64",
                "win": "neutral",
            }.get(platform)
            if requested_arch is None:
                raise FetchError("unsupported WinGet platform")
            installer = select_winget_installer(data, requested_arch)
            assets.append(
                _asset(
                    platform,
                    installer.get("InstallerUrl", data.get("InstallerUrl")),
                    installer.get("InstallerSha256", data.get("InstallerSha256")),
                )
            )
    else:
        raise FetchError("unknown manifest provider")
    if not assets or not version:
        raise FetchError("manifest has no release version or assets")
    return FetchResult(
        id="",
        name=package,
        version=str(version),
        source=f"{provider} manifest: {package}",
        version_source=f"{provider} package manifest version",
        homepage=homepage,
        assets=assets,
    )
