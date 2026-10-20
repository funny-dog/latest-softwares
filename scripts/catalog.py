"""目录完整性和必收录覆盖报告，不依赖网络。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from app_core.downloads import asset_available
from scripts.config_loader import load_packages_config
from scripts.fetchers.base import AssetInfo, FetchResult, VERSION_KIND_SYNC_DATE

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "config" / "coverage.json"

# 允许用"长期例外"豁免门禁的 verification 状态。
# 只认上游主动拒绝访问的情况（反爬/限流），这类失败不代表链接真的失效；
# failed（404/410）等真实失效状态不在其中，仍会阻塞发布。
EXEMPTABLE_STATUSES = {"restricted"}


def _exemption_issue(
    required_entry: dict[str, Any],
    assets: dict[str, dict[str, Any]],
    platforms: set[str],
    now: datetime | None,
) -> str | None:
    """判断该条目能否用配置里的长期例外豁免门禁。

    返回 None 表示可以豁免；返回字符串说明为什么不行（写进报告，便于排查）。

    配置形状（config/coverage.json 的 required 项）：
        "exemptions": {
            "reason": "Adobe 官网对自动访问返回 403",
            "review_by": "2027-01-01"
        }

    设计取舍：只允许"上游拒绝访问"这类状态豁免。真实失效（failed，如 404/410）
    不在 EXEMPTABLE_STATUSES 里，因此仍会阻塞发布——否则等于把死链放行。
    """
    exemption = required_entry.get("exemptions")
    if not isinstance(exemption, dict):
        return "no_exemption_configured"

    review_by = exemption.get("review_by")
    if review_by:
        try:
            deadline = datetime.fromisoformat(str(review_by)).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return "bad_review_by"
        current = now or datetime.now(timezone.utc)
        if current > deadline:
            return f"exemption_expired:{review_by}"

    for platform in sorted(platforms):
        asset = assets.get(platform)
        if asset is None:
            return f"missing_platform:{platform}"
        status = (asset.get("verification") or {}).get("status")
        if status not in EXEMPTABLE_STATUSES:
            return f"status_not_exemptable:{platform}={status}"
    return None



def expected_platforms(entry: dict[str, Any]) -> list[str]:
    args = entry.get("args", {})
    if entry.get("fetcher") == "windows11_fido":
        return [f"win-{args.get('arch', 'x64')}"]
    for key in ("assets", "platforms", "builds"):
        if args.get(key):
            return [item["platform"] for item in args[key]]
    return ["win-x64"]


def fallback_record(entry: dict[str, Any], reason: str) -> dict[str, Any] | None:
    homepage = entry.get("homepage")
    if not homepage:
        return None
    result = FetchResult(
        id=entry["id"],
        name=entry["name"],
        category=entry["category"],
        homepage=homepage,
        version=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        version_kind=VERSION_KIND_SYNC_DATE,
        version_source="official page fallback; release version unavailable",
        source="Official page fallback; pending verification",
        assets=[
            AssetInfo(platform=p, url=homepage, link_kind="landing_page")
            for p in expected_platforms(entry)
        ],
    ).to_dict()
    for asset in result["assets"]:
        asset["verification"] = {
            "status": "unverified",
            "reason": "official page fallback pending verification",
        }
    for key in ("editions", "desc_cn", "desc_en"):
        if key in entry:
            result[key] = entry[key]
    result.update(_stale=True, _stale_reason=reason)
    return result


def load_baseline() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(BASELINE.read_text(encoding="utf-8")))


def coverage_report(
    entries: list[dict[str, Any]],
    data: dict[str, Any],
    baseline: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    configured = {p["id"]: p for p in entries}
    published = {p["id"]: p for p in data.get("packages", [])}
    required = {p["id"]: p for p in baseline.get("required", [])}
    problems = []
    gate_errors = []
    exempted_required: list[dict[str, Any]] = []
    covered = 0
    for pid in sorted(configured.keys() | required.keys()):
        entry = configured.get(pid)
        package = published.get(pid)
        issues = []
        if entry is None:
            issues.append("missing_catalog")
        if package is None:
            issues.append("missing_data")
        required_entry = required.get(pid, {})
        if entry is not None:
            editions = set(entry.get("editions", ["cn", "intl"]))
            if set(required_entry.get("editions", [])) - editions:
                issues.append("missing_editions")
        if package:
            if set(required_entry.get("editions", [])) - set(
                package.get("editions", ["cn", "intl"])
            ):
                issues.append("missing_published_editions")
            assets = {a["platform"]: a for a in package.get("assets", [])}
            platforms = set(required_entry.get("platforms", [])) or set(
                expected_platforms(entry or package)
            )
            for platform in sorted(platforms):
                asset = assets.get(platform)
                if asset is None:
                    issues.append(f"missing_platform:{platform}")
                elif not asset.get("verification") or not asset_available(asset, now):
                    issues.append(f"unverified_or_unavailable:{platform}")
        if issues:
            problems.append({"id": pid, "required": pid in required, "issues": issues})
            if pid in required or "missing_data" in issues:
                # 长期例外：只有"上游拒绝访问"能被豁免，真实失效仍阻塞。
                # 注意 package is None（缺数据）时不允许豁免——那是同步失败，不是反爬。
                exempted: str | None = "not_applicable"
                if pid in required and package is not None:
                    exempted = _exemption_issue(
                        required_entry,
                        {a["platform"]: a for a in package.get("assets", [])},
                        set(required_entry.get("platforms", []))
                        or set(expected_platforms(entry or package)),
                        now,
                    )
                if pid in required and exempted is None:
                    exempted_required.append(
                        {
                            "id": pid,
                            "reason": str(
                                (required_entry.get("exemptions") or {}).get(
                                    "reason", ""
                                )
                            ),
                            "review_by": (required_entry.get("exemptions") or {}).get(
                                "review_by"
                            ),
                        }
                    )
                else:
                    gate_errors.append(pid)
                    if exempted and exempted != "no_exemption_configured":
                        problems[-1]["exemption_blocked_by"] = exempted
        elif pid in required:
            covered += 1
    extras = sorted(published.keys() - configured.keys())
    gate_errors.extend(extras)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "configured": len(configured),
        "published": len(published),
        "stale_packages": sum(bool(p.get("_stale")) for p in published.values()),
        "verified_assets": sum(
            bool(a.get("verification")) and asset_available(a, now)
            for p in published.values()
            for a in p.get("assets", [])
        ),
        "unavailable_assets": sum(
            not a.get("verification") or not asset_available(a, now)
            for p in published.values()
            for a in p.get("assets", [])
        ),
        "required_total": len(required),
        "required_covered": covered,
        "required_coverage": covered / len(required) if required else 1.0,
        "obsolete_ids": extras,
        "problems": problems,
        "gate_errors": sorted(set(gate_errors)),
        "required_exemptions": exempted_required,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/latest.json")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/coverage-report.json"
    )
    parser.add_argument("--gate", action="store_true")
    args = parser.parse_args(argv)
    report = coverage_report(
        load_packages_config()["packages"],
        json.loads(args.data.read_text(encoding="utf-8")),
        load_baseline(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "problems"}, ensure_ascii=True
        )
    )
    return int(args.gate and bool(report["gate_errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
