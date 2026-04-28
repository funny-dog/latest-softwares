from __future__ import annotations

import json
import re

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


def test_json_injection_records_requested_edition(tmp_path, monkeypatch):
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
                "schema_version": 2,
                "packages": [
                    {"id": "cn-only", "editions": ["cn"]},
                    {"id": "intl-only", "editions": ["intl"]},
                ],
                "stats": {},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(build_web, "DIST", dist)
    monkeypatch.setattr(build_web, "DATA_FILE", data_file)

    build_web.inject_data(edition="intl")

    html = index.read_text(encoding="utf-8")
    assert '"edition":"intl"' in html
    assert '"id":"intl-only"' in html
    assert '"id":"cn-only"' not in html


def test_web_source_uses_local_vendor_assets():
    html = (build_web.WEB_SRC / "index.html").read_text(encoding="utf-8")

    assert "https://cdn.tailwindcss.com" not in html
    assert "https://cdn.jsdelivr.net" not in html
    assert "https://fonts.googleapis.com" not in html
    assert "https://fonts.gstatic.com" not in html
    assert 'src="vendor/tailwindcss.js"' in html
    assert 'src="vendor/alpinejs.min.js"' in html
    assert 'src="vendor/fuse.min.js"' in html


def test_copy_static_copies_vendor_directory(tmp_path, monkeypatch):
    web_src = tmp_path / "web"
    vendor = web_src / "vendor"
    dist = tmp_path / "dist"
    vendor.mkdir(parents=True)
    dist.mkdir()
    (web_src / "index.html").write_text("index", encoding="utf-8")
    (vendor / "library.js").write_text("console.log('ok')", encoding="utf-8")

    monkeypatch.setattr(build_web, "WEB_SRC", web_src)
    monkeypatch.setattr(build_web, "DIST", dist)

    copied = build_web.copy_static()

    assert copied == 2
    assert (dist / "index.html").read_text(encoding="utf-8") == "index"
    assert (dist / "vendor" / "library.js").read_text(
        encoding="utf-8"
    ) == "console.log('ok')"


def test_vendor_manifest_checksums_match_real_files():
    verified = build_web.verify_vendor_assets()

    assert {entry["path"] for entry in verified} == {
        "vendor/tailwindcss.js",
        "vendor/alpinejs.min.js",
        "vendor/fuse.min.js",
    }
    for entry in verified:
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])


def test_web_app_uses_generated_at_for_last_updated():
    app_js = (build_web.WEB_SRC / "app.js").read_text(encoding="utf-8")

    assert "data.generated_at" in app_js


def test_web_shows_visible_version_kind_label():
    html = (build_web.WEB_SRC / "index.html").read_text(encoding="utf-8")

    assert 'x-text="versionKindLabel(pkg.version_kind)"' in html
    assert "pkg.version_source" in html


def test_web_index_uses_i18n_for_visible_copy():
    html = (build_web.WEB_SRC / "index.html").read_text(encoding="utf-8")

    assert "statusText()" in html
    assert "resultCountText()" in html
    assert "msg('direct_download'" in html
    assert "t('footer')" in html
