"""把新条目追加写入 packages/<edition>.yaml。

追加而非全量重写：只在文件尾部新增 list item，保证 PR diff 干净
（不动既有条目的格式/顺序）。
"""

from __future__ import annotations

from pathlib import Path
import os

import yaml


def append_entries(entries: list[dict], path: Path) -> None:
    """将新条目追加到 YAML 文件的 packages 列表末尾。

    采用字符串追加方式，避免全量重写导致 PR diff 过大。
    """
    if not entries:
        return
    text = path.read_text(encoding="utf-8") if path.exists() else "packages: []\n"
    existing = yaml.safe_load(text)
    if not isinstance(existing, dict) or not isinstance(existing.get("packages"), list):
        raise ValueError("packages must be a YAML list")
    if not text.endswith("\n"):
        text += "\n"
    chunk = yaml.safe_dump(
        entries,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        indent=2,
    )
    combined = text + chunk
    try:
        yaml.safe_load(combined)
    except yaml.YAMLError:
        combined = yaml.safe_dump(
            {**existing, "packages": existing["packages"] + entries},
            allow_unicode=True,
            sort_keys=False,
        )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(combined, encoding="utf-8")
    os.replace(temporary, path)
