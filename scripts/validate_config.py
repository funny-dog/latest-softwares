"""Validate packages.yaml before running network-heavy sync tasks."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

# Windows runner 默认 cp1252，print 中文（"配置校验通过"等）会 UnicodeEncodeError
# 进而 exit 1，让本应通过的校验在 CI 上崩溃。与 sync.py / render.py 模式一致：
# 在最早机会 reconfigure stdio 为 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.fetchers import FETCHERS  # type: ignore
    from scripts.link_utils import LINK_KINDS  # type: ignore
    from scripts.editions import validate_editions  # type: ignore
else:
    from .fetchers import FETCHERS
    from .link_utils import LINK_KINDS
    from .editions import validate_editions


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_FILE = REPO_ROOT / "packages.yaml"
PACKAGES_DIR = REPO_ROOT / "packages"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

FIXED_URL_FETCHERS = {
    "steam_official",
    "baidunetdisk",
    "download_page",
    "geek",
    "everything",
    "wechat_official",
}

REDIRECT_FETCHERS = {
    "wegame_official",
    "nvidia_app",
    "qq_official",
    "yy_official",
}


def _label(entry: dict, index: int) -> str:
    return str(entry.get("id") or f"#{index + 1}")


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_valid_url(value: object) -> bool:
    if not _is_nonempty_string(value):
        return False
    parsed = urlparse(str(value))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _require_string(errors: list[str], label: str, data: dict, key: str) -> None:
    if not _is_nonempty_string(data.get(key)):
        errors.append(f"{label}: 缺少或为空字段 {key}")


def _require_url(errors: list[str], label: str, data: dict, key: str) -> None:
    if not _is_valid_url(data.get(key)):
        errors.append(f"{label}: {key} 不是有效 URL")


def _validate_unique_platforms(
    errors: list[str],
    label: str,
    items: list[dict],
) -> None:
    seen: set[str] = set()
    for item in items:
        platform = item.get("platform")
        if not _is_nonempty_string(platform):
            continue
        if platform in seen:
            errors.append(f"{label}: 重复 platform: {platform}")
        seen.add(platform)


def _validate_link_kind(errors: list[str], label: str, item: dict) -> None:
    value = item.get("link_kind")
    if value is not None and value not in LINK_KINDS:
        errors.append(f"{label}: link_kind 必须是 direct 或 landing_page")


def _validate_list(
    errors: list[str],
    label: str,
    args: dict,
    key: str,
) -> list[dict]:
    items = args.get(key)
    if not isinstance(items, list) or not items:
        errors.append(f"{label}: args.{key} 必须是非空列表")
        return []
    bad_indexes = [i + 1 for i, item in enumerate(items) if not isinstance(item, dict)]
    if bad_indexes:
        errors.append(f"{label}: args.{key} 第 {bad_indexes} 项不是对象")
        return [item for item in items if isinstance(item, dict)]
    return items


def _validate_github_release(errors: list[str], label: str, args: dict) -> None:
    repo = args.get("repo")
    if not _is_nonempty_string(repo) or "/" not in str(repo):
        errors.append(f"{label}: args.repo 必须形如 owner/repo")

    tag_pattern = args.get("tag_pattern")
    if tag_pattern is not None:
        if not _is_nonempty_string(tag_pattern):
            errors.append(f"{label}: tag_pattern 不能为空")
        else:
            try:
                re.compile(str(tag_pattern))
            except re.error as exc:
                errors.append(f"{label}: tag_pattern 不是有效正则: {exc}")

    scan_pages = args.get("release_scan_pages")
    if scan_pages is not None:
        if (
            isinstance(scan_pages, bool)
            or not isinstance(scan_pages, int)
            or scan_pages < 1
        ):
            errors.append(f"{label}: release_scan_pages 必须是正整数")

    assets = _validate_list(errors, label, args, "assets")
    _validate_unique_platforms(errors, label, assets)
    for asset in assets:
        _require_string(errors, label, asset, "platform")
        _require_string(errors, label, asset, "pattern")
        _validate_link_kind(errors, label, asset)


def _validate_windows11_fido(errors: list[str], label: str, args: dict) -> None:
    _require_string(errors, label, args, "lang")
    _require_string(errors, label, args, "edition")
    arch = args.get("arch")
    if arch is not None and not _is_nonempty_string(arch):
        errors.append(f"{label}: arch 不能为空")


def _validate_vscode(errors: list[str], label: str, args: dict) -> None:
    builds = _validate_list(errors, label, args, "builds")
    _validate_unique_platforms(errors, label, builds)
    for build in builds:
        _require_string(errors, label, build, "platform")
        _require_string(errors, label, build, "build")
        _validate_link_kind(errors, label, build)


def _validate_chrome(errors: list[str], label: str, args: dict) -> None:
    platforms = _validate_list(errors, label, args, "platforms")
    _validate_unique_platforms(errors, label, platforms)
    for platform in platforms:
        _require_string(errors, label, platform, "platform")
        _require_string(errors, label, platform, "os_key")
        _require_string(errors, label, platform, "channel")
        _require_url(errors, label, platform, "download_url")
        _validate_link_kind(errors, label, platform)


def _validate_firefox(errors: list[str], label: str, args: dict) -> None:
    platforms = _validate_list(errors, label, args, "platforms")
    _validate_unique_platforms(errors, label, platforms)
    for platform in platforms:
        _require_string(errors, label, platform, "platform")
        _require_string(errors, label, platform, "os")
        _validate_link_kind(errors, label, platform)


def _validate_nodejs(errors: list[str], label: str, args: dict) -> None:
    platforms = _validate_list(errors, label, args, "platforms")
    _validate_unique_platforms(errors, label, platforms)
    for platform in platforms:
        _require_string(errors, label, platform, "platform")
        _require_string(errors, label, platform, "file_key")
        _require_string(errors, label, platform, "filename")
        _validate_link_kind(errors, label, platform)


def _validate_release_directory(errors: list[str], label: str, args: dict) -> None:
    platforms = _validate_list(errors, label, args, "platforms")
    _validate_unique_platforms(errors, label, platforms)
    for platform in platforms:
        _require_string(errors, label, platform, "platform")
        _require_string(errors, label, platform, "pattern")
        _validate_link_kind(errors, label, platform)

    edition_path = args.get("edition_path")
    if edition_path is not None and not _is_nonempty_string(edition_path):
        errors.append(f"{label}: edition_path 不能为空")


def _validate_fixed_url_platforms(errors: list[str], label: str, args: dict) -> None:
    platforms = _validate_list(errors, label, args, "platforms")
    _validate_unique_platforms(errors, label, platforms)
    for platform in platforms:
        _require_string(errors, label, platform, "platform")
        _require_url(errors, label, platform, "download_url")
        _validate_link_kind(errors, label, platform)


def _validate_redirect_platforms(errors: list[str], label: str, args: dict) -> None:
    platforms = args.get("platforms", [])
    if platforms is None:
        platforms = []
    if not isinstance(platforms, list):
        errors.append(f"{label}: args.platforms 必须是列表")
        return
    bad_indexes = [
        i + 1 for i, item in enumerate(platforms) if not isinstance(item, dict)
    ]
    if bad_indexes:
        errors.append(f"{label}: args.platforms 第 {bad_indexes} 项不是对象")
        platforms = [item for item in platforms if isinstance(item, dict)]
    _validate_unique_platforms(errors, label, platforms)
    for platform in platforms:
        _require_string(errors, label, platform, "platform")
        if "download_url" in platform:
            _require_url(errors, label, platform, "download_url")
        _validate_link_kind(errors, label, platform)


def _validate_fetcher_args(
    errors: list[str],
    label: str,
    fetcher_name: str,
    args: dict,
) -> None:
    if fetcher_name == "github_release":
        _validate_github_release(errors, label, args)
    elif fetcher_name == "windows11_fido":
        _validate_windows11_fido(errors, label, args)
    elif fetcher_name == "vscode_official":
        _validate_vscode(errors, label, args)
    elif fetcher_name == "chrome_official":
        _validate_chrome(errors, label, args)
    elif fetcher_name == "firefox_official":
        _validate_firefox(errors, label, args)
    elif fetcher_name == "nodejs_official":
        _validate_nodejs(errors, label, args)
    elif fetcher_name in {"ubuntu_releases", "fedora_releases"}:
        _validate_release_directory(errors, label, args)
    elif fetcher_name in FIXED_URL_FETCHERS:
        _validate_fixed_url_platforms(errors, label, args)
    elif fetcher_name in REDIRECT_FETCHERS:
        _validate_redirect_platforms(errors, label, args)


def validate_cross_file_uniqueness(packages_dir: Path) -> list[str]:
    """检查 packages/ 目录下所有文件的 id 唯一性"""
    errors: list[str] = []
    seen_ids: set[str] = set()

    for yaml_file in sorted(packages_dir.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            continue
        for pkg in data.get("packages", []):
            if not isinstance(pkg, dict):
                continue
            pkg_id = pkg.get("id")
            if pkg_id in seen_ids:
                errors.append(f"重复的 id '{pkg_id}' 在 {yaml_file.name} 中")
            seen_ids.add(pkg_id)

    return errors


def validate_config(config: dict) -> list[str]:
    """Return validation errors for a loaded packages.yaml document."""
    errors: list[str] = []
    if not isinstance(config, dict):
        return ["packages.yaml 必须是 YAML 对象"]

    packages = config.get("packages")
    if not isinstance(packages, list) or not packages:
        return ["packages 必须是非空列表"]

    seen_ids: set[str] = set()
    for index, entry in enumerate(packages):
        if not isinstance(entry, dict):
            errors.append(f"#{index + 1}: package 条目必须是对象")
            continue

        label = _label(entry, index)
        package_id = entry.get("id")
        if not _is_nonempty_string(package_id):
            errors.append(f"{label}: 缺少或为空字段 id")
        elif not ID_RE.fullmatch(str(package_id)):
            errors.append(f"{label}: id 只能包含小写字母、数字和连字符")
        elif package_id in seen_ids:
            errors.append(f"{label}: 重复 id: {package_id}")
        else:
            seen_ids.add(str(package_id))

        _require_string(errors, label, entry, "name")
        _require_string(errors, label, entry, "category")

        editions_err = validate_editions(entry.get("editions"))
        if editions_err:
            errors.append(f"{label}: {editions_err}")

        if "homepage" in entry:
            _require_url(errors, label, entry, "homepage")

        fetcher_name = entry.get("fetcher")
        if not _is_nonempty_string(fetcher_name):
            errors.append(f"{label}: 缺少或为空字段 fetcher")
            continue
        if fetcher_name not in FETCHERS:
            errors.append(f"{label}: 未知 fetcher: {fetcher_name}")
            continue

        args = entry.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            errors.append(f"{label}: args 必须是对象")
            continue
        _validate_fetcher_args(errors, label, str(fetcher_name), args)

    return errors


def main() -> int:
    config = yaml.safe_load(PACKAGES_FILE.read_text(encoding="utf-8"))
    errors = validate_config(config)

    # 检查 packages/ 目录下跨文件 id 唯一性
    if PACKAGES_DIR.is_dir():
        cross_file_errors = validate_cross_file_uniqueness(PACKAGES_DIR)
        errors.extend(cross_file_errors)

    if errors:
        print("packages.yaml 配置校验失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("packages.yaml 配置校验通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
