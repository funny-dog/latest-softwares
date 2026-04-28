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
        "| Total | Direct | Landing pages | OK | Fixed | Failed |",
        "|---:|---:|---:|---:|---:|---:|",
        (
            f"| {stats.get('total', 0)} | {stats.get('direct', 0)} | "
            f"{stats.get('landing_page', 0)} | {stats.get('ok', 0)} | "
            f"{stats.get('fixed', 0)} | {stats.get('failed', 0)} |"
        ),
    ]

    notable = [
        row
        for row in report.get("links", [])
        if row.get("status") in {"failed", "fixed"}
    ]
    if notable:
        lines.extend(
            [
                "",
                "| Package | Platform | Kind | Status | URL | Note |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in notable:
            note = row.get("error") or row.get("final_url") or ""
            lines.append(
                "| "
                f"`{_table_escape(row.get('id'))}` | "
                f"`{_table_escape(row.get('platform'))}` | "
                f"`{_table_escape(row.get('kind'))}` | "
                f"`{_table_escape(row.get('status'))}` | "
                f"{_table_escape(row.get('url'))} | "
                f"{_table_escape(note)} |"
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
