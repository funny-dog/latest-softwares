"""测试 vendor 更新脚本 —— 全部 mock 网络。"""

from __future__ import annotations

import hashlib
import json

import pytest

from scripts import update_vendor


def _make_manifest_dir(tmp_path, files: dict[str, bytes]):
    """构造一个临时 web/vendor 布局并返回 manifest 路径。"""
    vendor = tmp_path / "web" / "vendor"
    vendor.mkdir(parents=True)
    assets = []
    for name, content in files.items():
        (vendor / name).write_bytes(content)
        assets.append(
            {
                "path": f"vendor/{name}",
                "source": f"https://example.test/{name}",
                "sha256": hashlib.sha256(content).hexdigest(),
                "version": "1.0.0",
                "license": "MIT",
            }
        )
    manifest = vendor / "manifest.json"
    manifest.write_text(json.dumps({"assets": assets}, indent=2) + "\n")
    return vendor, manifest


def _patch_paths(monkeypatch, vendor, manifest):
    monkeypatch.setattr(update_vendor, "WEB_VENDOR", vendor)
    monkeypatch.setattr(update_vendor, "MANIFEST", manifest)
    monkeypatch.setattr(update_vendor, "REPO_ROOT", vendor.parent.parent)


def test_check_mode_passes_when_sha256_matches(tmp_path, monkeypatch, capsys):
    content = b"console.log('hi');\n"
    vendor, manifest = _make_manifest_dir(tmp_path, {"foo.js": content})
    _patch_paths(monkeypatch, vendor, manifest)
    monkeypatch.setattr(update_vendor, "_download", lambda url: content)
    monkeypatch.setattr("sys.argv", ["update_vendor"])

    rc = update_vendor.main()

    out = capsys.readouterr().out
    assert rc == 0
    assert "✓" in out
    assert "vendor/foo.js" in out


def test_check_mode_fails_on_sha256_drift(tmp_path, monkeypatch, capsys):
    content = b"original\n"
    vendor, manifest = _make_manifest_dir(tmp_path, {"foo.js": content})
    _patch_paths(monkeypatch, vendor, manifest)
    # 远端已被改动 —— 模拟 supply-chain 攻击
    monkeypatch.setattr(update_vendor, "_download", lambda url: b"malicious payload\n")
    monkeypatch.setattr("sys.argv", ["update_vendor"])

    rc = update_vendor.main()

    err = capsys.readouterr()
    assert rc == 1
    assert "sha256 不匹配" in err.out


def test_update_mode_writes_new_content_and_sha256(tmp_path, monkeypatch, capsys):
    old = b"v1\n"
    new = b"v2-with-fixes\n"
    vendor, manifest_path = _make_manifest_dir(tmp_path, {"foo.js": old})
    _patch_paths(monkeypatch, vendor, manifest_path)
    monkeypatch.setattr(update_vendor, "_download", lambda url: new)
    monkeypatch.setattr("sys.argv", ["update_vendor", "--update"])

    rc = update_vendor.main()

    assert rc == 0
    assert (vendor / "foo.js").read_bytes() == new
    updated = json.loads(manifest_path.read_text())
    assert updated["assets"][0]["sha256"] == hashlib.sha256(new).hexdigest()


def test_update_mode_does_not_save_manifest_on_failure(tmp_path, monkeypatch):
    """有任何下载失败时不应保存 manifest 半成品。"""
    content = b"unchanged\n"
    vendor, manifest_path = _make_manifest_dir(tmp_path, {"foo.js": content})
    _patch_paths(monkeypatch, vendor, manifest_path)
    original_manifest = manifest_path.read_text()

    def fake_download(url):
        raise TimeoutError("network down")

    monkeypatch.setattr(update_vendor, "_download", fake_download)
    monkeypatch.setattr("sys.argv", ["update_vendor", "--update"])

    rc = update_vendor.main()

    assert rc == 1
    assert manifest_path.read_text() == original_manifest


def test_check_mode_detects_local_file_corruption(tmp_path, monkeypatch, capsys):
    """远端 sha256 对得上 manifest，但本地文件被篡改 → 也应失败。"""
    content = b"good\n"
    vendor, manifest = _make_manifest_dir(tmp_path, {"foo.js": content})
    (vendor / "foo.js").write_bytes(b"locally tampered\n")  # 本地损坏
    _patch_paths(monkeypatch, vendor, manifest)
    monkeypatch.setattr(update_vendor, "_download", lambda url: content)
    monkeypatch.setattr("sys.argv", ["update_vendor"])

    rc = update_vendor.main()

    out = capsys.readouterr().out
    assert rc == 1
    assert "本地文件缺失或与远端不一致" in out


def test_missing_manifest_returns_error(tmp_path, monkeypatch):
    vendor = tmp_path / "web" / "vendor"
    vendor.mkdir(parents=True)
    manifest = vendor / "manifest.json"  # 不创建
    _patch_paths(monkeypatch, vendor, manifest)
    monkeypatch.setattr("sys.argv", ["update_vendor"])

    assert update_vendor.main() == 1


def test_manifest_requires_version_and_license(tmp_path, monkeypatch, capsys):
    vendor = tmp_path / "web" / "vendor"
    vendor.mkdir(parents=True)
    content = b"console.log('hi');\n"
    (vendor / "foo.js").write_bytes(content)
    manifest = vendor / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "path": "vendor/foo.js",
                        "source": "https://example.test/foo.js",
                        "sha256": hashlib.sha256(content).hexdigest(),
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _patch_paths(monkeypatch, vendor, manifest)
    monkeypatch.setattr(update_vendor, "_download", lambda url: content)
    monkeypatch.setattr("sys.argv", ["update_vendor"])

    rc = update_vendor.main()

    err = capsys.readouterr().err
    assert rc == 1
    assert "manifest.json 校验失败" in err
    assert "version" in err
    assert "license" in err


def test_real_vendor_manifest_has_version_and_license():
    manifest = json.loads(update_vendor.MANIFEST.read_text(encoding="utf-8"))

    missing = [
        asset.get("path")
        for asset in manifest.get("assets", [])
        if not asset.get("version") or not asset.get("license")
    ]
    assert not missing


def test_tailwind_vendor_source_is_pinned():
    manifest = json.loads(update_vendor.MANIFEST.read_text(encoding="utf-8"))
    tailwind = next(
        asset
        for asset in manifest.get("assets", [])
        if asset.get("path") == "vendor/tailwindcss.js"
    )

    assert tailwind["version"] in tailwind["source"]
    assert tailwind["source"] != "https://cdn.tailwindcss.com"


@pytest.mark.parametrize(
    "data,expected_prefix",
    [(b"abc", "ba7816bf"), (b"", "e3b0c442")],
)
def test_sha256_helper(data, expected_prefix):
    assert update_vendor._sha256(data).startswith(expected_prefix)
