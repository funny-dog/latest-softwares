"""检查仓库已提交验证快照的新鲜度；不请求上游或修改发布数据。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_core.downloads import parse_time

ROOT = Path(__file__).resolve().parents[1]


def check_publication(
    data: dict, now: datetime, max_age_hours: float
) -> tuple[int, str]:
    verified = parse_time(data.get("verified_at"))
    if verified is None or not data.get("release_id"):
        return 1, "No verified publication snapshot found."
    age = (now - verified).total_seconds() / 3600
    message = (
        f"Verified snapshot: {data['release_id']}; verified_at={verified.isoformat()}; "
        f"age={age:.1f}h; limit={max_age_hours:g}h."
    )
    failed = age > max_age_hours or age < -5 / 60
    return int(failed), message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/latest.json")
    parser.add_argument("--max-age-hours", type=float, default=24)
    args = parser.parse_args(argv)
    if args.max_age_hours <= 0:
        parser.error("max-age-hours must be positive")
    data = json.loads(args.data.read_text(encoding="utf-8"))
    code, message = check_publication(
        data, datetime.now(timezone.utc), args.max_age_hours
    )
    print(("::error::Publication stalled: " if code else "") + message)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write("## Publication freshness\n\n" + message + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
