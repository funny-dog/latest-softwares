"""将 packages.yaml 中的软件 ID 按 round-robin 分成 N 组。

用于 GitHub Actions matrix 策略并行化 sync。输出 JSON 数组，
每组是一个逗号分隔的 ID 字符串，可直接传给 sync.py --only。

用法：
  python scripts/partition_ids.py 3          # 分 3 组，输出 JSON
  python scripts/partition_ids.py 3 --edition intl  # 只取国际版
"""

from __future__ import annotations

import argparse
import json
import sys

# 兼容 Windows runner（cp1252 默认编码）下的非 ASCII 输出。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
from itertools import cycle
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.config_loader import load_packages_config  # type: ignore
else:
    from .config_loader import load_packages_config


def partition_ids(ids: list[str], n: int) -> list[str]:
    """Round-robin 分组，返回 n 个逗号分隔的 ID 字符串。"""
    groups: list[list[str]] = [[] for _ in range(n)]
    for idx, pid in enumerate(cycle(range(n))):
        if idx >= len(ids):
            break
        groups[pid].append(ids[idx])
    return [",".join(g) for g in groups if g]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shards", type=int, help="分组数量")
    parser.add_argument(
        "--edition",
        choices=["cn", "intl"],
        default=None,
        help="只取指定版本的软件 ID。",
    )
    args = parser.parse_args()

    cfg = load_packages_config()
    entries = cfg.get("packages", [])

    if args.edition:
        entries = [
            e for e in entries if args.edition in e.get("editions", [])
        ]

    ids = [e["id"] for e in entries]
    if not ids:
        print("没有任何软件 ID", file=sys.stderr)
        return 1

    groups = partition_ids(ids, args.shards)
    print(json.dumps(groups))
    return 0


if __name__ == "__main__":
    sys.exit(main())
