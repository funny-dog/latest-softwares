from __future__ import annotations

from pathlib import Path

import yaml

from scripts.discover.yaml_writer import append_entries


def test_append_entries_preserves_existing_and_adds(tmp_path: Path):
    f = tmp_path / "shared.yaml"
    f.write_text(
        "packages:\n"
        "- id: existing\n"
        "  name: Existing\n"
        "  category: Utilities\n"
        "  editions:\n"
        "  - cn\n"
        "  - intl\n"
        "  fetcher: github_release\n"
        "  args:\n"
        "    repo: foo/existing\n"
        "    assets:\n"
        "    - platform: win-x64\n"
        "      pattern: existing-*.exe\n"
        "  desc_cn: 旧\n"
        "  desc_en: old\n",
        encoding="utf-8",
    )
    new = [
        {
            "id": "rufus",
            "name": "Rufus",
            "category": "System Utilities",
            "editions": ["cn", "intl"],
            "homepage": "https://github.com/pbatard/rufus",
            "fetcher": "github_release",
            "args": {
                "repo": "pbatard/rufus",
                "assets": [{"platform": "win-x64", "pattern": "rufus-*.exe"}],
            },
            "desc_cn": "USB 启动盘制作工具",
            "desc_en": "USB tool",
        }
    ]
    append_entries(new, f)

    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    ids = [p["id"] for p in data["packages"]]
    assert ids == ["existing", "rufus"]
    # 中文不被转义
    assert "USB 启动盘制作工具" in f.read_text(encoding="utf-8")
