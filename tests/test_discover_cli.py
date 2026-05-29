from __future__ import annotations

from pathlib import Path

import yaml

from scripts.discover.yaml_writer import append_entries
from scripts import discover_popular


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


def test_cli_writes_entries_and_new_ids(tmp_path, monkeypatch):
    from scripts.discover.models import Candidate

    out = tmp_path / "shared.yaml"
    out.write_text(
        "packages:\n"
        "- id: seed\n"
        "  name: Seed\n"
        "  category: Utilities\n"
        "  editions:\n"
        "  - cn\n"
        "  - intl\n"
        "  fetcher: github_release\n"
        "  args:\n"
        "    repo: x/seed\n"
        "    assets:\n"
        "    - platform: win-x64\n"
        "      pattern: seed-*.exe\n"
        "  desc_cn: 种子\n"
        "  desc_en: seed\n",
        encoding="utf-8",
    )
    ids_file = tmp_path / "new_ids.txt"

    fake = [
        Candidate(
            repo="pbatard/rufus",
            name="Rufus",
            stars=29000,
            description="USB tool",
            asset_names=["rufus-4.5.exe"],
        )
    ]
    monkeypatch.setattr(discover_popular, "discover", lambda **kw: fake)
    monkeypatch.setattr(
        discover_popular,
        "select_candidates",
        lambda c, **kw: [(fake[0], "rufus-*.exe")],
    )
    monkeypatch.setattr(
        discover_popular, "categorize", lambda topics, desc: "System Utilities"
    )
    monkeypatch.setattr(
        discover_popular, "translate_to_zh", lambda t: "USB 启动盘制作工具"
    )

    rc = discover_popular.main(
        [
            "--output",
            str(out),
            "--new-ids-file",
            str(ids_file),
        ]
    )
    assert rc == 0
    assert ids_file.read_text(encoding="utf-8").strip() == "rufus"
    text = out.read_text(encoding="utf-8")
    assert "pbatard/rufus" in text
    assert "USB 启动盘制作工具" in text


def test_cli_no_candidates_writes_empty_ids(tmp_path, monkeypatch):
    out = tmp_path / "shared.yaml"
    out.write_text(
        "packages:\n"
        "- id: seed\n"
        "  name: Seed\n"
        "  category: Utilities\n"
        "  editions:\n"
        "  - cn\n"
        "  - intl\n"
        "  fetcher: github_release\n"
        "  args:\n"
        "    repo: x/seed\n"
        "    assets:\n"
        "    - platform: win-x64\n"
        "      pattern: seed-*.exe\n"
        "  desc_cn: 种子\n"
        "  desc_en: seed\n",
        encoding="utf-8",
    )
    ids_file = tmp_path / "new_ids.txt"
    monkeypatch.setattr(discover_popular, "discover", lambda **kw: [])
    monkeypatch.setattr(discover_popular, "select_candidates", lambda c, **kw: [])
    rc = discover_popular.main(["--output", str(out), "--new-ids-file", str(ids_file)])
    assert rc == 0
    assert ids_file.read_text(encoding="utf-8").strip() == ""
