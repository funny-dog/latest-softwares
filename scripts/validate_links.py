"""发布前验证并修复下载入口，保存按资产的检查状态与有界历史。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_core.downloads import asset_available, parse_time
from scripts.catalog import coverage_report, expected_platforms, load_baseline
from scripts.config_loader import load_packages_config
from scripts.fetchers import FETCHERS
from scripts.link_utils import is_direct_link
from scripts.link_verifier import verify_link
from scripts.net import set_max_connections_per_host

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = REPO_ROOT / "data/latest.json"
LINK_HEALTH_FILE = REPO_ROOT / "data/link-health.json"
MAX_WORKERS = 8
MAX_CONNECTIONS_PER_HOST = 8
VERIFICATION_POLICY_VERSION = 1
# 命中上游维护页时沿用旧验证结果，并把下次重试提前到这个间隔，避免上游
# 恢复后仍按 2~24 小时的退避干等。
MAINTENANCE_RETRY_MINUTES = 30


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _refetch_package(config: dict) -> dict | None:
    fetcher = FETCHERS.get(config.get("fetcher", ""))
    if not fetcher:
        return None
    try:
        result = fetcher(config.get("args", {}) or {}).to_dict()
        result["id"] = config["id"]
        for key in ("name", "category", "homepage", "editions", "desc_cn", "desc_en"):
            if key in config:
                result[key] = config[key]
        result["last_success_at"] = result["fetched_at"]
        return result
    except Exception as exc:
        print(f"Refetch {config['id']}: {type(exc).__name__}", file=sys.stderr)
        return None


def _fix_by_refetch(config: dict[str, Any], asset: dict[str, Any]) -> str | None:
    result = _refetch_package(config)
    if result:
        return next(
            (
                a["url"]
                for a in result["assets"]
                if a["platform"] == asset.get("platform")
            ),
            None,
        )
    return None


def _config_fingerprint(config: dict, asset: dict) -> str:
    payload = {
        "policy_version": VERIFICATION_POLICY_VERSION,
        "config": config,
        "platform": asset["platform"],
        "url": asset["url"],
        "kind": asset.get("link_kind"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def validate_and_fix(
    *,
    force: bool = False,
    budget: int = 2000,
    gate: bool = False,
    allow_unverified_required: set[str] | None = None,
    exception_reason: str = "",
) -> int:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    entries = load_packages_config()["packages"]
    configs = {p["id"]: p for p in entries}
    baseline = load_baseline()
    important = {p["id"] for p in baseline["required"]}
    allowed = allow_unverified_required or set()
    if allowed and (not gate or not exception_reason.strip()):
        raise ValueError("publication exceptions require --gate and a reason")
    if allowed - important:
        raise ValueError("publication exceptions must name required software")
    state_file = DATA_FILE.with_name("link-state.json")
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        state = {"schema_version": 1, "assets": {}}
    now = datetime.now(timezone.utc)
    report = {
        "schema_version": 2,
        "generated_at": now.isoformat(timespec="seconds"),
        "stats": {
            k: 0
            for k in (
                "total",
                "direct",
                "landing_page",
                "ok",
                "fixed",
                "fallback",
                "failed",
                "restricted",
                "transient",
                "unverified",
                "cached",
                "deferred",
            )
        },
        "links": [],
    }
    remaining = budget
    active_keys = set()
    prefetched = {}

    def check(asset: dict, config: dict) -> dict:
        nonlocal remaining
        key = f"{config['id']}:{asset['platform']}"
        active_keys.add(key)
        old = state["assets"].get(key, {})
        fingerprint = _config_fingerprint(config, asset)
        cached = old.get("verification", {})
        next_check = parse_time(old.get("next_check_at"))
        candidate = {**asset, "verification": cached}
        if (
            not force
            and old.get("fingerprint") == fingerprint
            and next_check
            and next_check > now
        ):
            if cached.get("status") != "verified" or asset_available(candidate, now):
                return {**cached, "cached": True}
        if fingerprint in prefetched:
            verification = prefetched.pop(fingerprint)
        else:
            if remaining <= 0:
                if old.get("fingerprint") == fingerprint and asset_available(
                    candidate, now
                ):
                    return {**cached, "deferred": True}
                return {
                    "status": "unverified",
                    "reason": "check budget exhausted",
                    "deferred": True,
                }
            remaining -= 1
            verification = verify_link(asset, config, now=now)
        attempt = dict(verification)
        # 失败次数按"本轮真实尝试结果"计，降级不改变退避语义。
        failures = 0 if attempt["status"] == "verified" else old.get("failures", 0) + 1
        # 短暂故障降级（沿用旧结果，不延长有效期、不算成功）：
        # 1) 网络异常/超时（已有行为，重试间隔仍按 failures 退避）；
        # 2) 上游整站维护页（transient）——既不是死链也不是反爬，硬判失败会让
        #    整条发布流水线卡到上游恢复为止，因此额外把重试提前。
        transient = attempt["status"] in {"unverified", "transient"} and (
            attempt["status"] == "transient"
            or attempt.get("reason", "").startswith("network check failed:")
        )
        # 优先用 link-state 的旧结果；缓存丢失时回退到快照自身仍有效的验证结果，
        # 否则一次 cache miss 就会把可用的已发布入口判成不可用。
        # 携带时先剥掉上一轮的瞬时标记，避免把历史尝试信息当成新结论。
        _transient_keys = {
            "last_attempt_at",
            "last_attempt_status",
            "last_attempt_reason",
        }
        snapshot_verification = asset.get("verification")
        if old.get("fingerprint") == fingerprint and asset_available(candidate, now):
            carry_over = {k: v for k, v in cached.items() if k not in _transient_keys}
        elif isinstance(snapshot_verification, dict) and asset_available(asset, now):
            carry_over = {
                k: v
                for k, v in snapshot_verification.items()
                if k not in _transient_keys
            }
        else:
            carry_over = None
        if transient and carry_over:
            verification = {
                **carry_over,
                "last_attempt_at": now.isoformat(timespec="seconds"),
                "last_attempt_status": attempt["status"],
                "last_attempt_reason": attempt.get("reason"),
            }
            retry_at = (
                now + timedelta(minutes=MAINTENANCE_RETRY_MINUTES)
                if attempt["status"] == "transient"
                else None
            )
        else:
            verification = attempt
            retry_at = None
        hours = (
            6
            if config["id"] in important
            else {"long_tail": 72, "standard": 24, "critical": 6}.get(
                config.get("priority"), 24
            )
        )
        if failures:
            hours = min(24, 2 ** min(failures, 4))
        next_at = now + timedelta(hours=hours)
        if retry_at and retry_at < next_at:
            next_at = retry_at
        expiry = parse_time(verification.get("valid_until"))
        if expiry:
            next_at = min(next_at, expiry)
        history = old.get("history", [])[-9:] + [
            {
                "at": now.isoformat(timespec="seconds"),
                "url": asset["url"],
                "status": attempt["status"],
                "reason": attempt.get("reason"),
            }
        ]
        state["assets"][key] = {
            "fingerprint": fingerprint,
            "verification": verification,
            "failures": failures,
            "next_check_at": next_at.isoformat(timespec="seconds"),
            "last_success_at": verification["checked_at"]
            if not failures
            else old.get("last_success_at"),
            "history": history,
        }
        return verification

    packages = {p["id"]: p for p in data["packages"]}
    # 批量并行只做首次网络检查；状态更新和修复保持顺序，避免同一软件元数据竞争。
    due = []
    for package in sorted(
        data["packages"],
        key=lambda p: (
            p["id"] not in important,
            state["assets"]
            .get(f"{p['id']}:{(p.get('assets') or [{}])[0].get('platform', '')}", {})
            .get("next_check_at", ""),
            p["id"],
        ),
    ):
        config = configs.get(package["id"])
        if not config:
            continue
        present = {a["platform"] for a in package.get("assets", [])}
        for platform in expected_platforms(config):
            if platform not in present and config.get("homepage"):
                package.setdefault("assets", []).append(
                    {
                        "platform": platform,
                        "url": config["homepage"],
                        "link_kind": "landing_page",
                        "fallback": True,
                    }
                )
        for asset in package.get("assets", []):
            key = f"{config['id']}:{asset['platform']}"
            old = state["assets"].get(key, {})
            next_at = parse_time(old.get("next_check_at"))
            if (
                not force
                and old.get("fingerprint") == _config_fingerprint(config, asset)
                and next_at
                and next_at > now
                and (
                    old.get("verification", {}).get("status") != "verified"
                    or asset_available(
                        {**asset, "verification": old.get("verification")}, now
                    )
                )
            ):
                continue
            due.append((asset, config))
    # 检查结果仅为本轮预取；check() 仍负责预算、历史和缓存。
    prefetch = due[:budget]
    set_max_connections_per_host(MAX_CONNECTIONS_PER_HOST)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(
            pool.map(lambda item: verify_link(item[0], item[1], now=now), prefetch)
        )
    prefetched.update(
        {_config_fingerprint(c, a): r for (a, c), r in zip(prefetch, results)}
    )
    remaining -= len(prefetch)
    for pid in sorted(packages, key=lambda value: value not in important):
        package = packages[pid]
        config = configs.get(pid)
        if not config:
            continue
        checked = [(a, check(a, config)) for a in package.get("assets", [])]
        broken = any(
            v["status"] != "verified" and not v.get("deferred") and not v.get("cached")
            for _, v in checked
        )
        repaired = False
        if (
            broken
            and config["fetcher"] not in {"download_page", "windows11_fido"}
            and remaining > 0
        ):
            fresh = _refetch_package(config)
            if fresh:
                fresh_checked = [(a, check(a, config)) for a in fresh["assets"]]
                # 完整包一起替换；缺失/失败的平台继续用旧包降级，不能混入不同版本的直链。
                expected = set(expected_platforms(config))
                if expected <= {
                    a["platform"] for a, v in fresh_checked if v["status"] == "verified"
                }:
                    packages[pid] = package = fresh
                    checked = fresh_checked
                    repaired = True
        for asset, verification in checked:
            fallback = False
            if (
                verification["status"] != "verified"
                and not verification.get("deferred")
                and config.get("homepage")
                and asset["url"] != config["homepage"]
            ):
                page = {
                    "platform": asset["platform"],
                    "url": config["homepage"],
                    "link_kind": "landing_page",
                    "fallback": True,
                }
                page_verification = check(page, config)
                if page_verification["status"] != "verified":
                    print(
                        f"Fallback {pid}:{asset['platform']}: "
                        f"{page_verification.get('reason', page_verification['status'])}",
                        file=sys.stderr,
                    )
                if page_verification["status"] == "verified":
                    asset.clear()
                    asset.update(page)
                    verification = page_verification
                    fallback = True
            asset["verification"] = {
                k: v for k, v in verification.items() if k not in {"cached", "deferred"}
            }
            direct = is_direct_link(asset["url"], asset.get("link_kind"))
            kind = "direct" if direct else "landing_page"
            report["stats"]["total"] += 1
            report["stats"][kind] += 1
            if verification.get("deferred"):
                status = "deferred"
            elif verification.get("cached"):
                status = "cached"
            elif verification["status"] == "verified":
                status = "fallback" if fallback else "fixed" if repaired else "ok"
            else:
                status = verification["status"]
            report["stats"][status] += 1
            report["links"].append(
                {
                    **asset["verification"],
                    "verification_status": verification["status"],
                    "id": pid,
                    "platform": asset["platform"],
                    "kind": kind,
                    "status": status,
                    "url": asset["url"],
                }
            )
    data["packages"] = [packages[p["id"]] for p in data["packages"]]
    data["release_id"] = hashlib.sha256(
        json.dumps(data["packages"], sort_keys=True).encode()
    ).hexdigest()[:20]
    data["checked_at"] = now.isoformat(timespec="seconds")
    coverage = coverage_report(entries, data, baseline, now=now)
    coverage["strict_gate_errors"] = list(coverage["gate_errors"])
    exceptions = []
    for problem in coverage["problems"]:
        if problem["id"] in allowed and all(
            issue.startswith("unverified_or_unavailable:")
            for issue in problem["issues"]
        ):
            coverage["gate_errors"].remove(problem["id"])
            exceptions.append(
                {
                    "id": problem["id"],
                    "reason": exception_reason.strip(),
                    "approved_by": os.environ.get("GITHUB_ACTOR", "local operator"),
                    "at": data["checked_at"],
                }
            )
    coverage["publication_exceptions"] = exceptions
    if not coverage["gate_errors"]:
        data["verified_at"] = data["checked_at"]
    else:
        data.pop("verified_at", None)
    data["quality"] = {
        key: coverage[key]
        for key in (
            "required_total",
            "required_covered",
            "verified_assets",
            "unavailable_assets",
            "stale_packages",
            "publication_exceptions",
        )
    }
    failed = [p for p in data["packages"] if p.get("_stale")]
    data["stats"] = {
        "total": len(configs),
        "success": len(data["packages"]) - len(failed),
        "failed": len(failed),
        "failed_ids": [p["id"] for p in failed],
        "failures": [
            {"id": p["id"], "error": p.get("_stale_reason", "metadata stale")}
            for p in failed
        ],
    }
    report["gate_errors"] = coverage["gate_errors"]
    report["strict_gate_errors"] = coverage["strict_gate_errors"]
    report["publication_exceptions"] = exceptions
    state["assets"] = {k: v for k, v in state["assets"].items() if k in active_keys}
    _write_json(DATA_FILE, data)
    _write_json(state_file, state)
    _write_json(LINK_HEALTH_FILE, report)
    _write_json(DATA_FILE.with_name("coverage-report.json"), coverage)
    print(json.dumps(report["stats"], ensure_ascii=True))
    if gate:
        return int(bool(coverage["gate_errors"]))
    return int(
        any(
            a["verification"]["status"] != "verified"
            for p in data["packages"]
            for a in p.get("assets", [])
            if p["id"] in configs
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="Ignore the incremental check schedule"
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=2000,
        help="Maximum HTTP verification operations per run",
    )
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Block publication on missing required software/entrypoints",
    )
    parser.add_argument(
        "--allow-unverified-required",
        default="",
        metavar="ID[,ID...]",
        help="Explicit per-run exception; entry stays present and unavailable",
    )
    parser.add_argument("--exception-reason", default="", help="Human approval reason")
    args = parser.parse_args(argv)
    if args.budget < 1:
        parser.error("budget must be positive")
    try:
        return validate_and_fix(
            force=args.force,
            budget=args.budget,
            gate=args.gate,
            allow_unverified_required={
                p.strip()
                for p in args.allow_unverified_required.split(",")
                if p.strip()
            },
            exception_reason=args.exception_reason,
        )
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    sys.exit(main())
