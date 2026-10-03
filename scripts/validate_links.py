"""下载链接校验与自动修复。

遍历 data/latest.json 中所有 asset URL，发送 HEAD 请求校验可达性。

增量检查：若上一份 data/link-health.json 中同一 (url, version) 已校验为 ok
且未超过 --max-age-days，则直接沿用结果、不再发请求（版本有变化的条目必然重查）。
--full 强制全量检查。

若发现失效链接（4xx/5xx），根据 fetcher 类型尝试自动修复：

  - 重新调用对应 fetcher，按相同 platform 查找最新 URL
  - 无法重新抓取或 URL 未变化时输出警告

修复后的数据写回 data/latest.json，供后续 render 使用。
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.fetchers import FETCHERS  # type: ignore
    from scripts.link_utils import (  # type: ignore
        LINK_KIND_DIRECT,
        LINK_KIND_LANDING_PAGE,
        is_direct_link,
    )
    from scripts.net import (  # type: ignore
        get,
        github_headers,
        head,
        set_max_connections_per_host,
    )
    from scripts.config_loader import load_packages_config  # type: ignore
else:
    from .fetchers import FETCHERS
    from .link_utils import LINK_KIND_DIRECT, LINK_KIND_LANDING_PAGE, is_direct_link
    from .net import get, github_headers, head, set_max_connections_per_host
    from .config_loader import load_packages_config

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
LINK_HEALTH_FILE = REPO_ROOT / "data" / "link-health.json"

TIMEOUT = 30
# URL 检查纯 I/O；95% 的直链都在 github.com，单 host 并发上限必须同步放开，
# 否则会被 net.py 默认的 4 连接/host 卡住，线程数再多也用不上。
MAX_WORKERS = 16
MAX_CONNECTIONS_PER_HOST = 16
DEFAULT_MAX_AGE_DAYS = 7


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _load_previous_ok(max_age_days: float) -> dict[tuple[str, str], str]:
    """读取上一份健康报告，返回仍在有效期内的 ok 结果：(url, version) → checked_at。"""
    try:
        report = json.loads(LINK_HEALTH_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(report, dict):
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    previous: dict[tuple[str, str], str] = {}
    for row in report.get("links", []):
        if not isinstance(row, dict) or row.get("status") != "ok":
            continue
        checked_at = row.get("checked_at")
        parsed = _parse_iso(checked_at)
        if parsed is None or parsed < cutoff:
            continue
        previous[(str(row.get("url", "")), str(row.get("version", "")))] = checked_at
    return previous


def _new_health_report(total: int, direct: int, landing_page: int) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "stats": {
            "total": total,
            "direct": direct,
            "landing_page": landing_page,
            "ok": 0,
            "fixed": 0,
            "failed": 0,
            "cached": 0,
        },
        "links": [],
    }


def _record_link(
    report: dict[str, Any],
    *,
    package_id: str,
    platform: str,
    kind: str,
    status: str,
    url: str,
    version: str | None = None,
    checked_at: str | None = None,
    final_url: str | None = None,
    error: str | None = None,
) -> None:
    row = {
        "id": package_id,
        "platform": platform,
        "kind": kind,
        "status": status,
        "url": url,
    }
    if version:
        row["version"] = version
    if checked_at:
        row["checked_at"] = checked_at
    if final_url and final_url != url:
        row["final_url"] = final_url
    if error:
        row["error"] = error
    report["links"].append(row)


def _write_health_report(report: dict[str, Any]) -> None:
    LINK_HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    LINK_HEALTH_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def validate_and_fix(
    *, full: bool = False, max_age_days: float = DEFAULT_MAX_AGE_DAYS
) -> int:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cfg = load_packages_config()
    configs = {entry["id"]: entry for entry in cfg.get("packages", [])}
    previous_ok = {} if full else _load_previous_ok(max_age_days)

    # ==== Phase 1: 收集所有待检查的直链 URL ====
    Check = tuple[dict, int, str, str, str]  # (pkg, asset_idx, eid, platform, url)
    checks: list[Check] = []
    cached: list[tuple[str, str, str, str, str]] = []  # (eid, platform, url, ver, at)
    landing_records: list[tuple[str, str, str]] = []  # (eid, platform, url)
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

            if not is_direct_link(url, asset.get("link_kind")):
                landing_count += 1
                landing_records.append((eid, asset.get("platform", ""), url))
                print(f"  ↗ {eid} [{asset.get('platform', '')}]: 跳转页，跳过验证")
                continue

            platform = asset.get("platform", "")
            version = str(pkg.get("version", ""))
            checked_at = previous_ok.get((url, version))
            if checked_at:
                cached.append((eid, platform, url, version, checked_at))
                continue
            checks.append((pkg, i, eid, platform, url))

    total_checked = len(checks) + len(cached) + landing_count
    health = _new_health_report(
        total=total_checked,
        direct=len(checks) + len(cached),
        landing_page=landing_count,
    )
    if cached:
        print(
            f"增量检查：{len(cached)} 个直链版本未变且 {max_age_days:g} 天内校验通过，"
            f"沿用结果；需实际检查 {len(checks)} 个"
        )

    for eid, platform, url, version, checked_at in cached:
        health["stats"]["ok"] += 1
        health["stats"]["cached"] += 1
        _record_link(
            health,
            package_id=eid,
            platform=platform,
            kind=LINK_KIND_DIRECT,
            status="ok",
            url=url,
            version=version,
            checked_at=checked_at,
        )

    for eid, platform, url in landing_records:
        _record_link(
            health,
            package_id=eid,
            platform=platform,
            kind=LINK_KIND_LANDING_PAGE,
            status="skipped",
            url=url,
        )

    # ==== Phase 2: 并行检查所有直链 URL ====
    failed_checks: list[Check] = []

    if checks:
        set_max_connections_per_host(MAX_CONNECTIONS_PER_HOST)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_check_url_robust, url): (pkg, i, eid, platform, url)
                for (pkg, i, eid, platform, url) in checks
            }
            for future in as_completed(futures):
                pkg, i, eid, platform, url = futures[future]
                ok = future.result()
                if ok:
                    health["stats"]["ok"] += 1
                    _record_link(
                        health,
                        package_id=eid,
                        platform=platform,
                        kind=LINK_KIND_DIRECT,
                        status="ok",
                        url=url,
                        version=str(pkg.get("version", "")),
                        checked_at=_utc_now_iso(),
                    )
                    print(f"  ✓ {eid} [{platform}]: 有效")
                else:
                    failed_checks.append((pkg, i, eid, platform, url))

    # ==== Phase 3: 串行修复失败链接（涉及 API 调用，不宜并发） ====
    total_fixed = 0
    total_failed = 0

    for pkg, i, eid, platform, url in failed_checks:
        print(f"  ✗ {eid} [{platform}]: 链接失效 {url}", file=sys.stderr)

        config = configs.get(eid)
        asset = pkg["assets"][i]

        fixed_url = _fix_by_refetch(config, asset)

        if fixed_url and fixed_url != url:
            pkg["assets"][i]["url"] = fixed_url
            total_fixed += 1
            health["stats"]["fixed"] += 1
            _record_link(
                health,
                package_id=eid,
                platform=platform,
                kind=LINK_KIND_DIRECT,
                status="fixed",
                url=url,
                final_url=fixed_url,
            )
            print(f"    ↳ 已修复 → {fixed_url}")
        else:
            total_failed += 1
            health["stats"]["failed"] += 1
            _record_link(
                health,
                package_id=eid,
                platform=platform,
                kind=LINK_KIND_DIRECT,
                status="failed",
                url=url,
                error="无法自动修复",
            )
            print("    ⚠ 无法自动修复", file=sys.stderr)

    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    _write_health_report(health)
    print(
        f"\n校验完成：检查 {total_checked} 个链接，修复 {total_fixed} 个，失败 {total_failed} 个"
    )
    return 0 if total_failed == 0 else 1


def _is_github_url(url: str) -> bool:
    """判断是否为 GitHub 相关 URL（release asset 下载或 API）。"""
    return "github.com" in url or "objects.githubusercontent.com" in url


def _check_url(url: str) -> bool:
    """HEAD 请求检查 URL 是否可达（2xx/3xx 视为有效）。"""
    extra = github_headers() if _is_github_url(url) else None
    try:
        resp = head(
            url,
            allow_redirects=True,
            timeout=TIMEOUT,
            retries=2,
            headers=extra,
        )
        return resp.status_code < 400
    except Exception:
        return False


def _check_url_get_fallback(url: str) -> bool:
    """GET + Range 字节请求作为备选（部分 CDN 拒绝 HEAD 但允许 GET）。"""
    headers: dict[str, str] = {"Range": "bytes=0-0"}
    if _is_github_url(url):
        headers.update(github_headers())
    try:
        resp = get(
            url,
            headers=headers,
            timeout=TIMEOUT,
            stream=True,
            retries=2,
        )
        resp.close()
        return resp.status_code < 400
    except Exception:
        return False


def _check_url_robust(url: str) -> bool:
    """HEAD 优先，失败则 GET+Range 备选。由 ThreadPoolExecutor 并发调用。"""
    return _check_url(url) or _check_url_get_fallback(url)


def _fix_by_refetch(config: dict[str, Any], asset: dict[str, Any]) -> str | None:
    """Refetch package metadata and return the URL for the same platform."""
    fetcher_name = config.get("fetcher", "")
    fetcher = FETCHERS.get(fetcher_name)
    if fetcher is None:
        return None

    platform = asset.get("platform", "")
    try:
        result = fetcher(config.get("args", {}) or {})
    except Exception as exc:
        print(f"    {fetcher_name} 重新抓取失败: {exc}", file=sys.stderr)
        return None

    for candidate in result.assets:
        if candidate.platform == platform:
            return candidate.url
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验下载直链并尝试自动修复")
    parser.add_argument(
        "--full",
        action="store_true",
        help="忽略上一份健康报告，全量检查所有直链",
    )
    parser.add_argument(
        "--max-age-days",
        type=float,
        default=DEFAULT_MAX_AGE_DAYS,
        help=f"沿用上次 ok 结果的最长天数（默认 {DEFAULT_MAX_AGE_DAYS}）",
    )
    args = parser.parse_args(argv)
    return validate_and_fix(full=args.full, max_age_days=args.max_age_days)


if __name__ == "__main__":
    sys.exit(main())
