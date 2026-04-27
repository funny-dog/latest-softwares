"""把 data/latest.json 渲染为 README.md。

模板用 Jinja2，避免在 Python 里拼大段 Markdown 字符串。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

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


def main() -> int:
    if not DATA_FILE.exists():
        print(f"找不到 {DATA_FILE}，请先运行 scripts/sync.py", file=sys.stderr)
        return 1

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    packages = data.get("packages", [])
    stats = data.get("stats", {})

    env = Environment(
        loader=FileSystemLoader(str(REPO_ROOT)),
        autoescape=select_autoescape(
            enabled_extensions=()
        ),  # Markdown 不需要 HTML 转义
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    env.filters["fmt_date"] = fmt_date

    tmpl = env.get_template(TEMPLATE_FILE.name)
    rendered = tmpl.render(
        updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        grouped=group_by_category(packages),
        total=stats.get("total", len(packages)),
        failed=stats.get("failed", 0),
    )
    OUTPUT_FILE.write_text(rendered, encoding="utf-8")
    print(
        f"写入 {OUTPUT_FILE.relative_to(REPO_ROOT)}（{len(packages)} 项软件，分 {len(group_by_category(packages))} 组）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
