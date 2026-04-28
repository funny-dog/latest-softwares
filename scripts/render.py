"""把 data/latest.json 渲染为 README.md。

模板用 Jinja2，避免在 Python 里拼大段 Markdown 字符串。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# 兼容两种运行方式
if __package__ in (None, ""):
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.editions import filter_data_by_edition, VALID_EDITIONS  # type: ignore
else:
    from .editions import filter_data_by_edition, VALID_EDITIONS

# 同 sync.py，Windows cp1252 默认编码会让 print 中文/emoji 崩。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = REPO_ROOT / "data" / "latest.json"
TEMPLATE_FILE = REPO_ROOT / "README.template.md"
OUTPUT_FILE = REPO_ROOT / "README.md"

UNCATEGORIZED = "其他"


def fmt_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        # 兼容 'YYYY-MM-DDTHH:MM:SSZ' 和 'YYYY-MM-DDTHH:MM:SS+00:00'
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return value


def group_by_category(packages: list[dict]) -> list[tuple[str, list[dict]]]:
    """按 category 分组，保留 packages.yaml 中首次出现的顺序。"""
    seen_order: list[str] = []
    buckets: dict[str, list[dict]] = {}
    for pkg in packages:
        cat = pkg.get("category") or UNCATEGORIZED
        if cat not in buckets:
            seen_order.append(cat)
            buckets[cat] = []
        buckets[cat].append(pkg)
    return [(cat, buckets[cat]) for cat in seen_order]


def _format_updated_at(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def _latest_fetched_at(packages: list[dict]) -> str | None:
    values = sorted(
        pkg.get("fetched_at", "") for pkg in packages if pkg.get("fetched_at")
    )
    return values[-1] if values else None


def render_markdown(data: dict) -> str:
    packages = data.get("packages", [])
    stats = data.get("stats", {})
    updated_at = (
        data.get("generated_at")
        or stats.get("generated_at")
        or _latest_fetched_at(packages)
    )

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_FILE.parent)),
        autoescape=select_autoescape(
            enabled_extensions=()
        ),  # Markdown 不需要 HTML 转义
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    env.filters["fmt_date"] = fmt_date

    tmpl = env.get_template(TEMPLATE_FILE.name)
    return tmpl.render(
        updated_at=_format_updated_at(updated_at),
        grouped=group_by_category(packages),
        total=stats.get("total", len(packages)),
        failed=stats.get("failed", 0),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="只检查 README.md 是否与模板和数据一致，不写文件",
    )
    parser.add_argument(
        "--edition",
        choices=sorted(VALID_EDITIONS),
        default=None,
        help="只渲染指定版本的软件（cn=国内版，intl=国际版）。",
    )
    args = parser.parse_args(argv)

    if not DATA_FILE.exists():
        print(f"找不到 {DATA_FILE}，请先运行 scripts/sync.py", file=sys.stderr)
        return 1

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    data = filter_data_by_edition(data, args.edition)
    packages = data["packages"]
    rendered = render_markdown(data)

    if args.check:
        if not OUTPUT_FILE.exists():
            print(f"找不到 {OUTPUT_FILE}", file=sys.stderr)
            return 1
        current = OUTPUT_FILE.read_text(encoding="utf-8")
        if current != rendered:
            print(
                f"{OUTPUT_FILE.relative_to(REPO_ROOT)} 与模板渲染结果不一致",
                file=sys.stderr,
            )
            return 1
        print(f"{OUTPUT_FILE.relative_to(REPO_ROOT)} 已是最新")
        return 0

    OUTPUT_FILE.write_text(rendered, encoding="utf-8")
    print(
        f"写入 {OUTPUT_FILE.relative_to(REPO_ROOT)}（{len(packages)} 项软件，分 {len(group_by_category(packages))} 组）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
