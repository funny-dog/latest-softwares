"""把 web/ 下源文件 + data/latest.json 组装为可部署的 dist/。

设计要点：
  - 数据通过字符串替换注入到 index.html 的 window.__PKG_DATA__，
    避免运行时再发一次 fetch 请求（首屏更快、不依赖文件路径）
  - dist/ 每次重建会先清空（避免上次残留文件）
  - 渲染产物的 mtime 对 rsync --delete 行为有影响，但 rsync 默认按
    内容判断变化，不会因 mtime 触发不必要的传输
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.http import get  # type: ignore
else:
    from .http import get

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
TIMEOUT = 30

# index.html 中数据占位符（必须与 web/index.html 内严格一致）
DATA_PLACEHOLDER = (
    '/*__DATA__*/ {"schema_version": 1, "packages": [], "stats": {}} /*__DATA__*/'
)
VENDOR_ASSETS = [
    {
        "url": "https://cdn.tailwindcss.com",
        "path": "vendor/tailwindcss.js",
    },
    {
        "url": "https://cdn.jsdelivr.net/npm/alpinejs@3.14.1/dist/cdn.min.js",
        "path": "vendor/alpinejs.min.js",
    },
    {
        "url": "https://cdn.jsdelivr.net/npm/fuse.js@7.0.0/dist/fuse.min.js",
        "path": "vendor/fuse.min.js",
    },
]


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
        if src.is_file():
            shutil.copy2(src, DIST / src.name)
            count += 1
    return count


def copy_vendor() -> int:
    """Download browser dependencies into dist/vendor for CDN-free deploys."""
    count = 0
    for asset in VENDOR_ASSETS:
        response = get(asset["url"], timeout=TIMEOUT)
        response.raise_for_status()
        target = DIST / asset["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        count += 1
    return count


def _json_for_inline_script(data: dict) -> str:
    """Encode JSON so it cannot break out of the surrounding script tag."""
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def rewrite_vendor_refs(html: str) -> str:
    for asset in VENDOR_ASSETS:
        html = html.replace(asset["url"], asset["path"])
    html = html.replace(
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n', ""
    )
    html = html.replace(
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n',
        "",
    )
    html = html.replace(
        '  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">\n',
        "",
    )
    return html


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

    html = rewrite_vendor_refs(html.replace(DATA_PLACEHOLDER, replacement))
    index.write_text(html, encoding="utf-8")
    return len(data.get("packages", []))


def main() -> int:
    if not WEB_SRC.exists():
        print(f"✗ 找不到 {WEB_SRC.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    DIST.mkdir(parents=True, exist_ok=True)
    clean_dist()
    n_files = copy_static()
    n_vendor = copy_vendor()
    n_pkgs = inject_data()

    print(
        f"✓ dist/ 构建完成（{n_files} 个静态文件，"
        f"{n_vendor} 个 vendor 文件，注入 {n_pkgs} 个软件数据）"
    )
    print(
        f"  本地预览: uv run python -m http.server -d {DIST.relative_to(REPO_ROOT)} 8000"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
