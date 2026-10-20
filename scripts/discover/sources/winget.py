"""WinGet 软件发现：按 publisher tree 和软件游标有界扫描，不执行 manifest。"""

from __future__ import annotations

import re
from typing import Any

import yaml

from ...fetchers.package_manifest import select_winget_installer
from ...fetchers.base import FetchError
from ...net import get, get_json, github_headers
from ..models import DEFAULT_MAX_SCAN, Candidate
from ..state import DiscoveryState
from ..url_utils import extract_github_repo, is_valid_http_url

_API = "https://api.github.com/repos/microsoft/winget-pkgs"
_PARTITIONS = "abcdefghijklmnopqrstuvwxyz0123456789"
LAST_ERROR: str | None = None


def parse_manifest_yaml(content: str) -> dict[str, Any] | None:
    try:
        value = yaml.safe_load(content)
        return value if isinstance(value, dict) else None
    except yaml.YAMLError:
        return None


def extract_installer_url(manifest: dict[str, Any]) -> tuple[str | None, str]:
    for arch, platform in (
        ("x64", "win-x64"),
        ("arm64", "win-arm64"),
        ("x86", "win-x86"),
        ("neutral", "win"),
    ):
        if not any(
            item.get("Architecture", manifest.get("Architecture")) == arch
            for item in manifest.get("Installers", [])
        ):
            continue
        try:
            installer = select_winget_installer(manifest, arch)
        except FetchError:
            return None, platform
        url = installer.get("InstallerUrl", manifest.get("InstallerUrl"))
        return (str(url), platform) if is_valid_http_url(url) else (None, platform)
    return None, "win"


def _version_key(value: str) -> tuple:
    return tuple(
        (1, int(v)) if v.isdigit() else (0, v.casefold())
        for v in re.split(r"(\d+)", value)
    )


def discover(
    max_scan: int = DEFAULT_MAX_SCAN,
    *,
    partition: str | None = None,
    cursor: int = 0,
    state: DiscoveryState | None = None,
) -> list[Candidate]:
    global LAST_ERROR
    LAST_ERROR = None
    saved = state.get_cursor("winget", {}) if state else {}
    part_idx = int(saved.get("partition_index", 0)) % len(_PARTITIONS)
    part = partition or _PARTITIONS[part_idx]
    publisher_idx = int(saved.get("publisher_index", 0))
    offset = int(saved.get("package_offset", cursor))
    candidates = []
    scanned = 0
    try:
        publishers = get_json(
            f"{_API}/contents/manifests/{part}", headers=github_headers(), timeout=30
        )
        if not isinstance(publishers, list):
            raise ValueError("invalid WinGet publisher directory")
        publishers = [p for p in publishers if p.get("type") == "dir"]
        while publisher_idx < len(publishers) and scanned < max_scan:
            publisher = publishers[publisher_idx]
            tree = get_json(
                f"{_API}/git/trees/{publisher['sha']}?recursive=1",
                headers=github_headers(),
                timeout=30,
            )
            if (
                not isinstance(tree, dict)
                or tree.get("truncated")
                or not isinstance(tree.get("tree"), list)
            ):
                raise ValueError("WinGet tree incomplete; narrower partition required")
            files = {f["path"] for f in tree["tree"] if f.get("type") == "blob"}
            latest = {}
            for path in sorted(files):
                if not path.endswith(".installer.yaml"):
                    continue
                name = path.rsplit("/", 1)[-1].removesuffix(".installer.yaml")
                version = path.split("/")[-2] if "/" in path else ""
                if name not in latest or _version_key(version) > _version_key(
                    latest[name][0]
                ):
                    latest[name] = (version, path)
            choices = sorted(latest.items())
            # 空 publisher 也消耗扫描预算，避免一轮无限遍历无效目录。
            if not choices:
                scanned += 1
            while offset < len(choices) and scanned < max_scan:
                package_id, (_, path) = choices[offset]
                scanned += 1
                base = f"https://raw.githubusercontent.com/microsoft/winget-pkgs/master/{publisher['path']}/"
                response = get(base + path, timeout=30)
                try:
                    manifest = parse_manifest_yaml(response.text) or {}
                finally:
                    response.close()
                if manifest.get("PackageIdentifier") != package_id:
                    raise ValueError("WinGet manifest identity mismatch")
                locale_path = (
                    path.removesuffix(".installer.yaml") + ".locale.en-US.yaml"
                )
                if locale_path in files:
                    response = get(base + locale_path, timeout=30)
                    try:
                        locale = parse_manifest_yaml(response.text) or {}
                    finally:
                        response.close()
                    if locale.get("PackageIdentifier") != package_id:
                        raise ValueError("WinGet locale identity mismatch")
                    manifest.update(locale)
                url, platform = extract_installer_url(manifest)
                homepage = str(manifest.get("PackageUrl") or "")
                candidates.append(
                    Candidate(
                        repo=extract_github_repo(homepage)
                        or extract_github_repo(url)
                        or "",
                        name=str(manifest.get("PackageName") or package_id),
                        description=str(
                            manifest.get("ShortDescription")
                            or manifest.get("Description")
                            or ""
                        ),
                        source="winget",
                        external_id=package_id,
                        homepage_url=homepage,
                        download_url=url or "",
                        platform=platform,
                        link_kind="direct",
                        fetcher="package_manifest",
                    )
                )
                offset += 1
                if state:
                    state.record_success(f"winget:{package_id}")
            if offset >= len(choices):
                publisher_idx += 1
                offset = 0
        if publisher_idx >= len(publishers):
            part_idx = (part_idx + 1) % len(_PARTITIONS)
            publisher_idx = offset = 0
    except Exception as exc:
        LAST_ERROR = str(exc)
        if state:
            state.record_retry(f"winget:partition:{part}", str(exc))
    if state:
        state.update_cursor(
            "winget",
            {
                "partition_index": part_idx,
                "publisher_index": publisher_idx,
                "package_offset": offset,
            },
        )
    return candidates
