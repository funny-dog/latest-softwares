"""把 web/ 下源文件 + data/latest.json 组装为可部署的 dist/。

设计要点：
  - 数据通过字符串替换注入到 index.html 的 window.__PKG_DATA__，
    避免运行时再发一次 fetch 请求（首屏更快、不依赖文件路径）
  - dist/ 每次重建会先清空（避免上次残留文件）
  - 渲染产物的 mtime 对 rsync --delete 行为有影响，但 rsync 默认按
    内容判断变化，不会因 mtime 触发不必要的传输
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

# Windows runner 默认 cp1252，输出 ✓ 会崩
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_SRC = REPO_ROOT / "web"
DATA_FILE = REPO_ROOT / "data" / "latest.json"
DIST = REPO_ROOT / "dist"
VENDOR_MANIFEST = WEB_SRC / "vendor" / "manifest.json"

# index.html 中数据占位符（必须与 web/index.html 内严格一致）
DATA_PLACEHOLDER = (
    '/*__DATA__*/ {"schema_version": 1, "packages": [], "stats": {}} /*__DATA__*/'
)


def clean_dist() -> None:
    if DIST.exists():
        for entry in DIST.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
    else:
        DIST.mkdir(parents=True)


def copy_static() -> int:
    count = 0
    for src in WEB_SRC.iterdir():
        target = DIST / src.name
        if src.is_file():
            shutil.copy2(src, target)
            count += 1
        elif src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
            count += sum(1 for path in src.rglob("*") if path.is_file())
    return count


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_vendor_assets() -> list[dict[str, str]]:
    """Validate vendored browser dependencies before copying them to dist."""
    if not VENDOR_MANIFEST.exists():
        raise FileNotFoundError(f"找不到 vendor manifest: {VENDOR_MANIFEST}")

    manifest = json.loads(VENDOR_MANIFEST.read_text(encoding="utf-8"))
    entries = manifest.get("assets", [])
    if not entries:
        raise RuntimeError("vendor manifest 没有配置任何 assets")

    verified: list[dict[str, str]] = []
    for entry in entries:
        rel_path = entry["path"]
        expected = entry["sha256"]
        asset_path = WEB_SRC / rel_path
        if not asset_path.is_file():
            raise FileNotFoundError(f"找不到 vendor 文件: {asset_path}")
        actual = _sha256(asset_path)
        if actual != expected:
            raise RuntimeError(
                f"vendor checksum 不匹配: {rel_path} expected={expected} actual={actual}"
            )
        verified.append({"path": rel_path, "sha256": actual})
    return verified


def _json_for_inline_script(data: dict) -> str:
    """Encode JSON so it cannot break out of the surrounding script tag."""
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def inject_data() -> int:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"找不到 {DATA_FILE.relative_to(REPO_ROOT)}，请先跑 scripts/sync.py"
        )
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    # ensure_ascii=False 让中文不被转义成 \uXXXX，体积更小
    data_json = _json_for_inline_script(data)
    replacement = f"/*__DATA__*/ {data_json} /*__DATA__*/"

    index = DIST / "index.html"
    html = index.read_text(encoding="utf-8")

    if DATA_PLACEHOLDER not in html:
        raise RuntimeError(
            "未在 index.html 找到数据占位符。"
            "请确认 web/index.html 的占位符与 build_web.py 中的 DATA_PLACEHOLDER 一致。"
        )

    html = html.replace(DATA_PLACEHOLDER, replacement)
    index.write_text(html, encoding="utf-8")
    return len(data.get("packages", []))


def main() -> int:
    if not WEB_SRC.exists():
        print(f"✗ 找不到 {WEB_SRC.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    DIST.mkdir(parents=True, exist_ok=True)
    clean_dist()
    vendor_assets = verify_vendor_assets()
    n_files = copy_static()
    n_pkgs = inject_data()

    print(
        f"✓ dist/ 构建完成（{n_files} 个静态文件，"
        f"{len(vendor_assets)} 个 vendor 文件已校验，注入 {n_pkgs} 个软件数据）"
    )
    print(
        f"  本地预览: uv run python -m http.server -d {DIST.relative_to(REPO_ROOT)} 8000"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
