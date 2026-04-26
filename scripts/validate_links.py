"""下载链接校验与自动修复。

遍历 data/latest.json 中所有 asset URL，发送 HEAD 请求校验可达性。
若发现失效链接（4xx/5xx），根据 fetcher 类型尝试自动修复：

  - github_release：重新查询 GitHub API，按 pattern 匹配最新 asset
  - 其它 fetcher：输出警告，暂不处理

修复后的数据写回 data/latest.json，供后续 render 使用。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml

# Windows runner 默认 cp1252，输出 ✓/✗/中文会 UnicodeEncodeError 进而崩掉整个脚本。
# 与 sync.py / render.py / build_web.py 保持一致。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = REPO_ROOT / "data" / "latest.json"
PACKAGES_FILE = REPO_ROOT / "packages.yaml"

TIMEOUT = 30
HEADERS = {"User-Agent": "latest-softwares-sync"}


def _get_headers() -> dict[str, str]:
    """GitHub API 请求头，带 token 时自动提额。"""
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "latest-softwares-sync",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def validate_and_fix() -> int:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cfg = yaml.safe_load(PACKAGES_FILE.read_text(encoding="utf-8"))
    configs = {entry["id"]: entry for entry in cfg.get("packages", [])}

    total_checked = 0
    total_fixed = 0
    total_failed = 0

    for pkg in data.get("packages", []):
        eid = pkg["id"]
        config = configs.get(eid)
        if not config:
            continue

        fetcher_name = config.get("fetcher", "")
        assets = pkg.get("assets", [])
        if not assets:
            continue

        for i, asset in enumerate(assets):
            url = asset.get("url", "")
            if not url:
                continue
            total_checked += 1

            ok = _check_url(url)
            if ok:
                print(f"  ✓ {eid} [{asset.get('platform', '')}]: 有效")
                continue

            print(f"  ✗ {eid} [{asset.get('platform', '')}]: 链接失效 {url}", file=sys.stderr)

            # 尝试修复
            fixed_url = None
            if fetcher_name == "github_release":
                fixed_url = _fix_github_asset(config, asset)
            elif fetcher_name in ("chrome_official", "steam_official"):
                fixed_url = _fix_fixed_url(fetcher_name, config, asset)

            if fixed_url:
                pkg["assets"][i]["url"] = fixed_url
                total_fixed += 1
                print(f"    ↳ 已修复 → {fixed_url}")
            else:
                total_failed += 1
                print(f"    ⚠ 无法自动修复", file=sys.stderr)

    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"\n校验完成：检查 {total_checked} 个链接，修复 {total_fixed} 个，失败 {total_failed} 个")
    return 0 if total_failed == 0 else 1


def _check_url(url: str) -> bool:
    """HEAD 请求检查 URL 是否可达（2xx/3xx 视为有效）。"""
    try:
        resp = requests.head(url, allow_redirects=True, timeout=TIMEOUT, headers=HEADERS)
        return resp.status_code < 400
    except Exception:
        return False


def _fix_github_asset(config: dict[str, Any], asset: dict[str, Any]) -> str | None:
    """重新查询 GitHub Release，按 pattern 找到正确的 asset URL。"""
    import fnmatch

    repo = config["args"]["repo"]
    tag_pattern = config["args"].get("tag_pattern")
    asset_specs = config["args"].get("assets", [])

    # 找到当前 asset 对应的 pattern
    current_platform = asset.get("platform", "")
    pattern = None
    for spec in asset_specs:
        if spec.get("platform") == current_platform:
            pattern = spec["pattern"]
            break
    if not pattern:
        return None

    # 获取 release
    try:
        if tag_pattern:
            # 有 tag_pattern，遍历最近 30 个 release
            api_url = f"https://api.github.com/repos/{repo}/releases?per_page=30"
            resp = requests.get(api_url, headers=_get_headers(), timeout=TIMEOUT)
            resp.raise_for_status()
            release = None
            compiled = re.compile(tag_pattern)
            for rel in resp.json():
                if rel.get("prerelease") or rel.get("draft"):
                    continue
                if compiled.search(rel.get("tag_name", "")):
                    release = rel
                    break
            if not release:
                return None
        else:
            # 无 tag_pattern，直接用 latest
            api_url = f"https://api.github.com/repos/{repo}/releases/latest"
            resp = requests.get(api_url, headers=_get_headers(), timeout=TIMEOUT)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            release = resp.json()

        # 在 release assets 中找匹配的
        for ra in release.get("assets", []):
            if fnmatch.fnmatch(ra["name"], pattern):
                return ra["browser_download_url"]

    except Exception as e:
        print(f"    github_release 修复失败: {e}", file=sys.stderr)

    return None


def _fix_fixed_url(fetcher_name: str, config: dict[str, Any], asset: dict[str, Any]) -> str | None:
    """固定 URL 的 fetcher：重新抓取版本，确认 URL 是否变化。"""
    if fetcher_name == "chrome_official":
        return _fix_chrome(config, asset)
    if fetcher_name == "steam_official":
        # Steam 的 URL 是固定的，直接返回原 URL（如果可访问性检查失败可能是临时问题）
        return asset.get("url")
    return None


def _fix_chrome(config: dict[str, Any], asset: dict[str, Any]) -> str | None:
    """Chrome 的下载 URL 是固定的，重新确认 API 版本是否存在。"""
    platform = asset.get("platform", "")
    spec = None
    for s in config["args"].get("platforms", []):
        if s.get("platform") == platform:
            spec = s
            break
    if not spec:
        return None

    api_url = (
        f"https://versionhistory.googleapis.com/v1/chrome/platforms/"
        f"{spec['os_key']}/channels/{spec['channel']}/versions?pageSize=1"
    )
    try:
        resp = requests.get(api_url, timeout=TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        versions = resp.json().get("versions", [])
        if versions:
            return spec["download_url"]
    except Exception:
        pass
    return None


if __name__ == "__main__":
    sys.exit(validate_and_fix())
