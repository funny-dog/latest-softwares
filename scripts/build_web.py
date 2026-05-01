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
import os
import shutil
import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.link_utils import DIRECT_FILE_EXTENSIONS  # type: ignore
    from scripts.editions import filter_data_by_edition, VALID_EDITIONS  # type: ignore
    from scripts.config_loader import load_packages_config  # type: ignore
else:
    from .link_utils import DIRECT_FILE_EXTENSIONS
    from .editions import filter_data_by_edition, VALID_EDITIONS
    from .config_loader import load_packages_config

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
VERSIONED_ASSETS = (
    "styles.css",
    "vendor/tailwindcss.js",
    "vendor/alpinejs.min.js",
    "vendor/fuse.min.js",
    "app.js",
)

# index.html 中数据占位符（必须与 web/index.html 内严格一致）
DATA_PLACEHOLDER = (
    '/*__DATA__*/ {"schema_version": 2, "packages": [], "stats": {}} /*__DATA__*/'
)
PUBLIC_SITE_URL = "https://latest-softwares-064facea.fastapicloud.dev"
CN_PUBLIC_SITE_URL = os.environ.get("CN_PUBLIC_SITE_URL", "http://localhost:8080")


ASSET_MANIFEST = WEB_SRC / "dist" / "asset-manifest.json"


def run_frontend_build() -> dict[str, str] | None:
    """运行前端构建，返回 asset manifest。

    Returns:
        Asset manifest 字典，如果构建失败返回 None。
    """
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            print(
                f"⚠ 前端构建失败，使用原文件: {result.stderr.strip()}",
                file=sys.stderr,
            )
            return None

        if ASSET_MANIFEST.exists():
            return json.loads(ASSET_MANIFEST.read_text(encoding="utf-8"))
        return None
    except FileNotFoundError:
        print("⚠ Node.js 未安装，使用原文件", file=sys.stderr)
        return None


def clean_dist() -> None:
    if DIST.exists():
        for entry in DIST.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
    else:
        DIST.mkdir(parents=True)


def copy_static(skip: set[str] | None = None) -> int:
    """复制 web/ 静态文件到 dist/。

    Args:
        skip: 要跳过的顶层文件名集合（如已由前端构建处理的 hashed 文件）。
    """
    skip = skip or set()
    count = 0
    for src in WEB_SRC.iterdir():
        if src.name in skip:
            continue
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


def inject_asset_versions() -> dict[str, str]:
    """Append content-hash query strings to static asset URLs in dist/index.html."""
    index = DIST / "index.html"
    html = index.read_text(encoding="utf-8")
    versions: dict[str, str] = {}

    for asset in VERSIONED_ASSETS:
        asset_path = DIST / asset
        if not asset_path.is_file():
            continue

        version = _sha256(asset_path)[:12]
        versions[asset] = version
        for attr in ("href", "src"):
            html = html.replace(
                f'{attr}="{asset}"',
                f'{attr}="{asset}?v={version}"',
            )

    index.write_text(html, encoding="utf-8")
    return versions


def _copy_hashed_assets(manifest: dict[str, str]) -> None:
    """从 web/dist/ 复制 hashed 资源到 dist/ 并更新 index.html 引用。"""
    src_dist = WEB_SRC / "dist"
    for original_name, hashed_name in manifest.items():
        src_file = src_dist / hashed_name
        if src_file.is_file():
            shutil.copy2(src_file, DIST / hashed_name)

    # 更新 index.html 中的资源引用
    index = DIST / "index.html"
    html = index.read_text(encoding="utf-8")
    for original_name, hashed_name in manifest.items():
        for attr in ("href", "src"):
            html = html.replace(
                f'{attr}="{original_name}"',
                f'{attr}="{hashed_name}"',
            )
    index.write_text(html, encoding="utf-8")


def _merge_desc_from_config(data: dict) -> None:
    """从 packages 配置合并 desc_cn/desc_en 到 data 中。"""
    cfg = load_packages_config()
    desc_map: dict[str, dict[str, str]] = {}
    for entry in cfg.get("packages", []):
        eid = entry.get("id")
        if not eid:
            continue
        desc: dict[str, str] = {}
        if "desc_cn" in entry:
            desc["desc_cn"] = entry["desc_cn"]
        if "desc_en" in entry:
            desc["desc_en"] = entry["desc_en"]
        if desc:
            desc_map[eid] = desc
    for pkg in data.get("packages", []):
        pkg_desc = desc_map.get(pkg.get("id"))
        if pkg_desc:
            pkg.update(pkg_desc)


def inject_data(edition: str | None = None) -> int:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"找不到 {DATA_FILE.relative_to(REPO_ROOT)}，请先跑 scripts/sync.py"
        )
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    _merge_desc_from_config(data)
    data = filter_data_by_edition(data, edition)
    data["direct_file_extensions"] = list(DIRECT_FILE_EXTENSIONS)
    if edition == "intl":
        data["public_site_url"] = PUBLIC_SITE_URL
    elif edition == "cn":
        data["public_site_url"] = CN_PUBLIC_SITE_URL
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
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--edition",
        choices=sorted(VALID_EDITIONS),
        default=None,
        help="只注入指定版本的软件数据（cn=国内版，intl=国际版）。",
    )
    args = parser.parse_args()

    if not WEB_SRC.exists():
        print(f"✗ 找不到 {WEB_SRC.relative_to(REPO_ROOT)}", file=sys.stderr)
        return 1

    DIST.mkdir(parents=True, exist_ok=True)
    clean_dist()
    vendor_assets = verify_vendor_assets()

    # 尝试运行前端构建管道（minify + hashed 文件名）
    asset_manifest = run_frontend_build()
    if asset_manifest:
        # 跳过已有 hashed 版本的源文件，避免覆盖
        skip_files = set(asset_manifest.keys())
        n_files = copy_static(skip=skip_files)
        _copy_hashed_assets(asset_manifest)
        n_files += len(asset_manifest)
        versioned_assets: dict[str, str] = {}
    else:
        n_files = copy_static()
        versioned_assets = inject_asset_versions()

    n_pkgs = inject_data(edition=args.edition)

    edition_label = f" [{args.edition}]" if args.edition else ""
    build_mode = "hashed" if asset_manifest else "legacy"
    print(
        f"✓ dist/ 构建完成{edition_label}（{n_files} 个静态文件，"
        f"{len(vendor_assets)} 个 vendor 文件已校验，"
        f"{len(versioned_assets)} 个静态资源已加版本，注入 {n_pkgs} 个软件数据"
        f"，构建模式: {build_mode}）"
    )
    print(f"  本地预览: python -m http.server -d {DIST.relative_to(REPO_ROOT)} 8000")
    return 0


if __name__ == "__main__":
    sys.exit(main())
