"""自动发现热门软件 CLI。

流程：GitHub 发现 → 编排过滤（资产+去重+佐证）→ 分类+翻译 → 组装条目
→ 追加写入 packages/<edition>.yaml → 校验 → 输出新增 id 列表（供 workflow 用）。

运行：
  python -m scripts.discover         # 包导入方式
  python scripts/discover_popular.py # 脚本方式
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Windows runner 默认 cp1252，输出中文/✓ 会 UnicodeEncodeError；与 sync.py 一致先 reconfigure。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.discover.sources.github import discover  # type: ignore
    from scripts.discover.aggregate import select_candidates  # type: ignore
    from scripts.discover.categorize import categorize  # type: ignore
    from scripts.discover.translate import translate_to_zh  # type: ignore
    from scripts.discover.generate import build_entry  # type: ignore
    from scripts.discover.yaml_writer import append_entries  # type: ignore
    from scripts.discover.models import (  # type: ignore
        DEFAULT_MIN_STARS,
        DEFAULT_MAX_OUTPUT,
        DEFAULT_MAX_SCAN,
        DEFAULT_MAX_CORROBORATE,
    )
    from scripts.config_loader import load_packages_config  # type: ignore
    from scripts.validate_config import validate_config  # type: ignore
else:
    from .discover.sources.github import discover
    from .discover.aggregate import select_candidates
    from .discover.categorize import categorize
    from .discover.translate import translate_to_zh
    from .discover.generate import build_entry
    from .discover.yaml_writer import append_entries
    from .discover.models import (
        DEFAULT_MIN_STARS,
        DEFAULT_MAX_OUTPUT,
        DEFAULT_MAX_SCAN,
        DEFAULT_MAX_CORROBORATE,
    )
    from .config_loader import load_packages_config
    from .validate_config import validate_config

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "packages" / "shared.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-stars", type=int, default=DEFAULT_MIN_STARS)
    parser.add_argument("--max-output", type=int, default=DEFAULT_MAX_OUTPUT)
    parser.add_argument("--max-scan", type=int, default=DEFAULT_MAX_SCAN)
    parser.add_argument("--max-corroborate", type=int, default=DEFAULT_MAX_CORROBORATE)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--new-ids-file", default=str(REPO_ROOT / "discover_new_ids.txt")
    )
    # argv 为 None 时 argparse 自动读 sys.argv[1:]；测试传显式列表。
    args = parser.parse_args(argv)

    candidates = discover(min_stars=args.min_stars, max_scan=args.max_scan)
    print(f"发现 {len(candidates)} 个高星候选")
    selected = select_candidates(
        candidates, max_output=args.max_output, max_corroborate=args.max_corroborate
    )
    print(f"过滤后保留 {len(selected)} 个候选")

    entries: list[dict] = []
    new_ids: list[str] = []
    seen_ids: set[str] = set()
    for cand, pattern in selected:
        entry = build_entry(
            repo=cand.repo,
            name=cand.name,
            category=categorize(cand.topics, cand.description),
            pattern=pattern,
            desc_en=cand.description,
            desc_cn=translate_to_zh(cand.description),
        )
        entry_id = entry["id"]
        # 跳过空 id 或批内重复 id：单个异常名不应让整轮校验失败而丢掉其它好候选。
        if not entry_id:
            print(
                f"⚠ 跳过 {cand.repo}：名称 {cand.name!r} 无法生成合法 id",
                file=sys.stderr,
            )
            continue
        if entry_id in seen_ids:
            print(
                f"⚠ 跳过 {cand.repo}：id {entry_id!r} 与本批其它候选冲突",
                file=sys.stderr,
            )
            continue
        seen_ids.add(entry_id)
        entries.append(entry)
        new_ids.append(entry_id)
        print(f"✓ {entry_id}: {cand.repo} ({cand.stars}★) → {pattern}")

    output_path = Path(args.output)
    if entries:
        append_entries(entries, output_path)
        # 写后校验：跨文件 id 唯一性 + 字段合法
        cfg = load_packages_config()
        errors = validate_config(cfg)
        if errors:
            print("生成的条目校验失败：", file=sys.stderr)
            for e in errors:
                print(f"- {e}", file=sys.stderr)
            return 1

    Path(args.new_ids_file).write_text("\n".join(new_ids), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
