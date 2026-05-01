"""合并多个 partial latest.json 为最终结果。

用于 GitHub Actions 矩阵并行 sync 后的合并步骤。
每个 shard 产出一个 partial latest.json（只含该 shard 同步的软件），
此脚本将它们合并，并从旧 data/latest.json 回填未出现在任何 shard 中的软件。

用法：
  python scripts/merge_results.py shard1/latest.json shard2/latest.json ...
  python scripts/merge_results.py --shards-dir /tmp/shards
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 兼容 Windows runner（cp1252 默认编码）下的非 ASCII 输出。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = REPO_ROOT / "data" / "latest.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_results(
    partials: list[dict],
    previous: dict[str, dict],
) -> dict:
    """合并多个 partial 结果，回填缺失的软件。"""
    merged: dict[str, dict] = {}

    for partial in partials:
        for pkg in partial.get("packages", []):
            pid = pkg["id"]
            # 如果多个 shard 都有同一个 id（不应发生），取最新的
            if pid in merged:
                existing_time = merged[pid].get("fetched_at", "")
                new_time = pkg.get("fetched_at", "")
                if new_time > existing_time:
                    merged[pid] = pkg
            else:
                merged[pid] = pkg

    # 回填：previous 中存在但本次没被任何 shard 处理的软件
    backfilled = 0
    for pid, entry in previous.items():
        if pid not in merged:
            stale = dict(entry)
            stale["_stale"] = True
            stale["_stale_reason"] = "not included in any sync shard"
            stale.setdefault("last_success_at", stale.get("fetched_at"))
            merged[pid] = stale
            backfilled += 1

    # 按 previous 的顺序排列（保持一致性），新增的排在末尾
    order = list(previous.keys())
    ordered = []
    for pid in order:
        if pid in merged:
            ordered.append(merged.pop(pid))
    ordered.extend(merged.values())

    # 统计
    total = len(ordered)
    stale_count = sum(1 for p in ordered if p.get("_stale"))
    success = total - stale_count

    result = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "packages": ordered,
        "stats": {
            "total": total,
            "success": success,
            "failed": stale_count,
            "failed_ids": [p["id"] for p in ordered if p.get("_stale")],
            "failures": [
                {
                    "id": p["id"],
                    "error": p.get("_stale_reason", "unknown"),
                }
                for p in ordered
                if p.get("_stale")
            ],
        },
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files",
        nargs="*",
        help="partial latest.json 文件路径。",
    )
    parser.add_argument(
        "--shards-dir",
        type=Path,
        help="包含多个 partial latest.json 的目录（自动扫描 *.json）。",
    )
    args = parser.parse_args()

    paths: list[Path] = []
    if args.shards_dir:
        # download-artifact 把每个 artifact 放在以 artifact 名命名的子目录中，
        # 如 shard-0/latest.json，需要递归扫描。
        paths.extend(sorted(args.shards_dir.glob("**/*.json")))
    paths.extend(Path(f) for f in args.files)

    if not paths:
        print("没有找到任何 partial 结果文件", file=sys.stderr)
        return 1

    partials = []
    for p in paths:
        try:
            partials.append(load_json(p))
            print(f"  加载 {p}: {len(partials[-1].get('packages', []))} 个软件")
        except Exception as e:
            print(f"  跳过 {p}: {e}", file=sys.stderr)

    if not partials:
        print("所有 partial 文件都无法加载", file=sys.stderr)
        return 1

    # 加载旧数据用于回填
    previous: dict[str, dict] = {}
    if DATA_FILE.exists():
        try:
            old = load_json(DATA_FILE)
            previous = {p["id"]: p for p in old.get("packages", [])}
            print(f"  加载旧数据: {len(previous)} 个软件")
        except Exception as e:
            print(f"  无法读取旧数据 {DATA_FILE}: {e}", file=sys.stderr)

    result = merge_results(partials, previous)

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    stats = result["stats"]
    print(
        f"\n合并完成: {stats['success']}/{stats['total']} 成功, "
        f"{stats['failed']} 个回填"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
