"""把新条目追加写入 packages/<edition>.yaml。

追加而非全量重写：只在文件尾部新增 list item，保证 PR diff 干净
（不动既有条目的格式/顺序）。
"""

from __future__ import annotations

from pathlib import Path

import yaml


def append_entries(entries: list[dict], path: Path) -> None:
    """将新条目追加到 YAML 文件的 packages 列表末尾。

    采用字符串追加方式，避免全量重写导致 PR diff 过大。
    """
    if not entries:
        return
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    chunk = yaml.safe_dump(
        entries,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        indent=2,
    )
    path.write_text(text + chunk, encoding="utf-8")
