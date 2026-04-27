from __future__ import annotations

import json

from scripts import build_web


def test_json_injection_escapes_script_end_tag(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    index = dist / "index.html"
    index.write_text(
        f"<script>window.__PKG_DATA__ = {build_web.DATA_PLACEHOLDER};</script>",
        encoding="utf-8",
    )
    data_file = tmp_path / "latest.json"
    data_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "packages": [{"id": "x", "name": "</script><script>alert(1)</script>"}],
                "stats": {},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(build_web, "DIST", dist)
    monkeypatch.setattr(build_web, "DATA_FILE", data_file)

    build_web.inject_data()

    html = index.read_text(encoding="utf-8")
    assert "</script><script>alert(1)</script>" not in html
    assert "<\\/script><script>alert(1)<\\/script>" in html


def test_rewrite_vendor_refs_points_to_local_dist_assets():
    html = """
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js"></script>
    """

    rewritten = build_web.rewrite_vendor_refs(html)

    assert "https://cdn.tailwindcss.com" not in rewritten
    assert "https://cdn.jsdelivr.net/npm/alpinejs" not in rewritten
    assert "https://cdn.jsdelivr.net/npm/fuse.js" not in rewritten
    assert "https://fonts.googleapis.com" not in rewritten
    assert "https://fonts.gstatic.com" not in rewritten
    assert 'src="vendor/tailwindcss.js"' in rewritten
    assert 'src="vendor/alpinejs.min.js"' in rewritten
    assert 'src="vendor/fuse.min.js"' in rewritten
