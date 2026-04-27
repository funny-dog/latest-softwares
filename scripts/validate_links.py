"""下载链接校验与自动修复。

遍历 data/latest.json 中所有 asset URL，发送 HEAD 请求校验可达性。
若发现失效链接（4xx/5xx），根据 fetcher 类型尝试自动修复：

  - github_release：重新查询 GitHub API，按 pattern 匹配最新 asset
  - 其它 fetcher：输出警告，暂不处理

修复后的数据写回 data/latest.json，供后续 render 使用。
"""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests
import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.http import get, get_json, github_headers, head  # type: ignore
else:
    from .http import get, get_json, github_headers, head

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
MAX_WORKERS = 15  # URL 检查纯 I/O，可开更多线程（比 sync 多，无 API 限流压力）

# 与 web/app.js isDirectLink() 保持一致的文件扩展名集合
_DIRECT_EXT_PATTERN = re.compile(
    r"\.(exe|dmg|iso|zip|tar\.gz|msi|pkg|deb|rpm|appimage|7z)$"
)


def _is_direct_link(url: str) -> bool:
    """判断 URL 是否为直链下载（与前端 isDirectLink 逻辑一致）。"""
    if not url:
        return False
    path = url.split("?")[0].lower()
    return bool(_DIRECT_EXT_PATTERN.search(path))


def validate_and_fix() -> int:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cfg = yaml.safe_load(PACKAGES_FILE.read_text(encoding="utf-8"))
    configs = {entry["id"]: entry for entry in cfg.get("packages", [])}

    # ==== Phase 1: 收集所有待检查的直链 URL ====
    Check = tuple[dict, int, str, str, str]  # (pkg, asset_idx, eid, platform, url)
    checks: list[Check] = []
    landing_count = 0

    for pkg in data.get("packages", []):
        eid = pkg["id"]
        config = configs.get(eid)
        if not config:
            continue
        assets = pkg.get("assets", [])
        if not assets:
            continue
        for i, asset in enumerate(assets):
            url = asset.get("url", "")
            if not url:
                continue

            if not _is_direct_link(url):
                landing_count += 1
                print(f"  ↗ {eid} [{asset.get('platform', '')}]: 跳转页，跳过验证")
                continue

            checks.append((pkg, i, eid, asset.get("platform", ""), url))

    total_checked = len(checks) + landing_count

    # ==== Phase 2: 并行检查所有直链 URL ====
    failed_checks: list[Check] = []

    if checks:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_check_url_robust, url): (pkg, i, eid, platform, url)
                for (pkg, i, eid, platform, url) in checks
            }
            for future in as_completed(futures):
                pkg, i, eid, platform, url = futures[future]
                ok = future.result()
                if ok:
                    print(f"  ✓ {eid} [{platform}]: 有效")
                else:
                    failed_checks.append((pkg, i, eid, platform, url))

    # ==== Phase 3: 串行修复失败链接（涉及 API 调用，不宜并发） ====
    total_fixed = 0
    total_failed = 0

    for pkg, i, eid, platform, url in failed_checks:
        print(f"  ✗ {eid} [{platform}]: 链接失效 {url}", file=sys.stderr)

        config = configs.get(eid)
        fetcher_name = config.get("fetcher", "") if config else ""
        asset = pkg["assets"][i]

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
            print("    ⚠ 无法自动修复", file=sys.stderr)

    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"\n校验完成：检查 {total_checked} 个链接，修复 {total_fixed} 个，失败 {total_failed} 个"
    )
    return 0 if total_failed == 0 else 1


def _check_url(url: str) -> bool:
    """HEAD 请求检查 URL 是否可达（2xx/3xx 视为有效）。"""
    try:
        resp = head(url, allow_redirects=True, timeout=TIMEOUT, retries=1)
        return resp.status_code < 400
    except Exception:
        return False


def _check_url_get_fallback(url: str) -> bool:
    """GET + Range 字节请求作为备选（部分 CDN 拒绝 HEAD 但允许 GET）。"""
    try:
        resp = get(
            url,
            headers={"Range": "bytes=0-0"},
            timeout=TIMEOUT,
            stream=True,
            retries=1,
        )
        resp.close()
        return resp.status_code < 400
    except Exception:
        return False


def _check_url_robust(url: str) -> bool:
    """HEAD 优先，失败则 GET+Range 备选。由 ThreadPoolExecutor 并发调用。"""
    return _check_url(url) or _check_url_get_fallback(url)


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
            # 有 tag_pattern，按 release_scan_pages 遍历 release 列表
            release = None
            compiled = re.compile(tag_pattern)
            scan_pages = max(1, int(config["args"].get("release_scan_pages", 1)))
            for page in range(1, scan_pages + 1):
                api_url = f"https://api.github.com/repos/{repo}/releases?per_page=30&page={page}"
                for rel in get_json(
                    api_url,
                    headers=github_headers(),
                    timeout=TIMEOUT,
                ):
                    if rel.get("prerelease") or rel.get("draft"):
                        continue
                    if compiled.search(rel.get("tag_name", "")):
                        release = rel
                        break
                if release:
                    break
            if not release:
                return None
        else:
            # 无 tag_pattern，直接用 latest
            api_url = f"https://api.github.com/repos/{repo}/releases/latest"
            try:
                release = get_json(api_url, headers=github_headers(), timeout=TIMEOUT)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    return None
                raise

        # 在 release assets 中找匹配的
        for ra in release.get("assets", []):
            if fnmatch.fnmatch(ra["name"], pattern):
                return ra["browser_download_url"]

    except Exception as e:
        print(f"    github_release 修复失败: {e}", file=sys.stderr)

    return None


def _fix_fixed_url(
    fetcher_name: str, config: dict[str, Any], asset: dict[str, Any]
) -> str | None:
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
        versions = get_json(api_url, timeout=TIMEOUT).get("versions", [])
        if versions:
            return spec["download_url"]
    except Exception:
        pass
    return None


if __name__ == "__main__":
    sys.exit(validate_and_fix())
