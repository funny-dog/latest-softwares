"""检查同步失败率，超过阈值时返回非零退出码"""

import json
import sys
from pathlib import Path


def check_sync_health(log_file: Path, max_fail_rate: float = 0.10) -> bool:
    """
    检查同步失败率

    Args:
        log_file: JSONL 日志文件路径
        max_fail_rate: 最大允许失败率（默认 10%）

    Returns:
        True 如果失败率在阈值内，False 否则
    """
    if not log_file.exists():
        return True

    total = 0
    failures = 0

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            total += 1
            if entry.get("status") == "fail":
                failures += 1

    if total == 0:
        return True

    fail_rate = failures / total
    return fail_rate <= max_fail_rate


def main() -> int:
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-fail-rate",
        type=float,
        default=0.10,
        help="最大允许失败率（默认 0.10，即 10%%）",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("data/sync_errors.jsonl"),
        help="JSONL 日志文件路径",
    )
    args = parser.parse_args()

    if check_sync_health(args.log_file, args.max_fail_rate):
        print(f"✓ 同步健康检查通过（失败率 ≤ {args.max_fail_rate:.0%}）")
        return 0
    else:
        print(f"✗ 同步失败率超过阈值（{args.max_fail_rate:.0%}）", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
