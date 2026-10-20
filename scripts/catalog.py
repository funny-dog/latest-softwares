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
                gate_errors.append(pid)
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
