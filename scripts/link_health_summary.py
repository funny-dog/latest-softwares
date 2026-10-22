"""Write a Markdown summary for data/link-health.json."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


def _table_escape(value: object) -> str:
    return str(value or "").replace("|", "\\|")


def render_summary(report: dict[str, Any]) -> str:
    stats = report.get("stats", {})
    lines = [
        "## Link Health",
        "",
        "| Total | Direct | Landing pages | OK | Fixed | Failed | Cached |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {stats.get('total', 0)} | {stats.get('direct', 0)} | "
            f"{stats.get('landing_page', 0)} | {stats.get('ok', 0)} | "
            f"{stats.get('fixed', 0)} | {stats.get('failed', 0)} | "
            f"{stats.get('cached', 0)} |"
        ),
    ]
    lines.extend(
        [
            "",
            "Additional states: "
            + ", ".join(
                f"{key}={stats.get(key, 0)}"
                for key in (
                    "fallback",
                    "restricted",
                    "transient",
                    "unverified",
                    "cached",
                    "deferred",
                )
            ),
        ]
    )
    if report.get("gate_errors"):
        lines.extend(["", "Publication blocked: " + ", ".join(report["gate_errors"])])
    if report.get("required_exemptions"):
        lines.extend(
            [
                "",
                "Restricted entries with configured exemptions (downloads stay disabled): "
                + ", ".join(item["id"] for item in report["required_exemptions"]),
            ]
        )
    coverage = report.get("coverage", {})
    if coverage:
        lines.extend(
            [
                "",
                f"Required coverage: {coverage['required_covered']}/{coverage['required_total']}; "
                f"unavailable assets (including cached): {coverage['unavailable_assets']}; "
                f"stale packages: {coverage['stale_packages']}",
            ]
        )

    notable = [
        row
        for row in report.get("links", [])
        if row.get("last_attempt_status")
        or row.get("verification_status") not in {None, "verified"}
        or row.get("status")
        in {
            "failed",
            "fixed",
            "fallback",
            "restricted",
            "transient",
            "unverified",
            "deferred",
        }
    ]
    notable.sort(key=lambda row: row.get("id") not in report.get("gate_errors", []))
    if notable:
        lines.extend(
            [
                "",
                "| Package | Platform | Kind | Status | URL | Note |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in notable:
            note = (
                row.get("last_attempt_reason")
                or row.get("error")
                or row.get("reason")
                or row.get("final_url")
                or ""
            )
            status = row.get("status")
            if status == "cached":
                status = f"cached/{row.get('verification_status', 'unknown')}"
            lines.append(
                "| "
                f"`{_table_escape(row.get('id'))}` | "
                f"`{_table_escape(row.get('platform'))}` | "
                f"`{_table_escape(row.get('kind'))}` | "
                f"`{_table_escape(status)}` | "
                f"{_table_escape(row.get('url'))} | "
                f"{_table_escape(note)} |"
            )
    if report.get("stale_packages"):
        lines.extend(
            ["", "### Stale metadata", "", "| Package | Reason |", "|---|---|"]
        )
        for package in report["stale_packages"]:
            lines.append(
                f"| `{_table_escape(package['id'])}` | {_table_escape(package['error'])} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to data/link-health.json")
    args = parser.parse_args(argv)

    report = json.loads(args.report.read_text(encoding="utf-8"))
    summary = render_summary(report)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as fh:
            fh.write(summary)
    else:
        sys.stdout.write(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
