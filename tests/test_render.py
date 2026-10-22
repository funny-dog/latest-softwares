from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from scripts import render


def test_render_check_detects_stale_output(tmp_path, monkeypatch):
    data_file = tmp_path / "latest.json"
    template_file = tmp_path / "README.template.md"
    output_file = tmp_path / "README.md"
    data_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "packages": [],
                "stats": {"total": 0, "failed": 0},
                "generated_at": "2026-01-02T03:04:05+00:00",
            }
        ),
        encoding="utf-8",
    )
    template_file.write_text(
        "updated={{ updated_at }} total={{ total }}\n", encoding="utf-8"
    )
    output_file.write_text("old\n", encoding="utf-8")

    monkeypatch.setattr(render, "DATA_FILE", data_file)
    monkeypatch.setattr(render, "README_ZH", (template_file, output_file))
    monkeypatch.setattr(render, "README_EN", (template_file, tmp_path / "README_en.md"))
    monkeypatch.setattr(render, "REPO_ROOT", tmp_path)

    rc = render.main(["--check"])

    assert rc == 1
    assert output_file.read_text(encoding="utf-8") == "old\n"


def test_render_check_accepts_current_output(tmp_path, monkeypatch):
    data_file = tmp_path / "latest.json"
    template_file = tmp_path / "README.template.md"
    output_file = tmp_path / "README.md"
    data_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "packages": [],
                "stats": {"total": 0, "failed": 0},
                "generated_at": "2026-01-02T03:04:05+00:00",
            }
        ),
        encoding="utf-8",
    )
    template_file.write_text(
        "updated={{ updated_at }} total={{ total }}\n", encoding="utf-8"
    )

    monkeypatch.setattr(render, "DATA_FILE", data_file)
    monkeypatch.setattr(render, "README_ZH", (template_file, output_file))
    monkeypatch.setattr(render, "README_EN", (template_file, tmp_path / "README_en.md"))
    monkeypatch.setattr(render, "REPO_ROOT", tmp_path)

    assert render.main([]) == 0
    assert render.main(["--check"]) == 0
    assert (
        output_file.read_text(encoding="utf-8")
        == "updated=2026-01-02 03:04:05 total=0\n"
    )


def test_current_readme_matches_template_and_data():
    assert render.main(["--check"]) == 0


def test_check_reproduces_snapshot_but_new_render_disables_expired_links(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(render, "REPO_ROOT", tmp_path)
    snapshot_time = datetime.now(timezone.utc) - timedelta(days=2)
    data = {
        "verified_at": snapshot_time.isoformat(),
        "packages": [
            {
                "id": "example",
                "assets": [
                    {
                        "url": "https://example.test/installer.exe",
                        "verification": {
                            "status": "verified",
                            "valid_until": (
                                snapshot_time + timedelta(days=1)
                            ).isoformat(),
                        },
                    }
                ],
            }
        ],
    }
    template = tmp_path / "template.md"
    template.write_text("{{ asset_available(grouped[0][1][0].assets[0]) }}")
    output = tmp_path / "output.md"
    output.write_text("True")
    assert render._render_one(data, template, output, check=True)
    assert render._render_one(data, template, output, check=False)
    assert output.read_text() == "False"


def test_render_includes_stale_reason():
    rendered = render.render_markdown(
        {
            "schema_version": 1,
            "generated_at": "2026-01-02T03:04:05+00:00",
            "packages": [
                {
                    "id": "windows11",
                    "name": "Windows 11",
                    "category": "操作系统",
                    "version": "25H2",
                    "source": "Microsoft Software Download",
                    "homepage": "https://example.test/",
                    "released_at": None,
                    "assets": [
                        {
                            "platform": "win-x64",
                            "url": "https://example.test/win11.iso",
                        }
                    ],
                    "_stale": True,
                    "_stale_reason": "未找到 pwsh",
                }
            ],
            "stats": {"total": 1, "failed": 1},
        },
        render.README_EN[0],
    )

    assert "未找到 pwsh" in rendered
