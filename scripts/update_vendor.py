"""下载并校验 web/vendor/ 下的本地化第三方 JS。

两种模式：
  - 默认（校验模式）：按 manifest.json 中的 source 拉取每个文件，
    若计算出的 sha256 与 manifest 中的 sha256 不一致 → 退出码 1，
    适合在 CI 中作为完整性巡检（防 supply-chain）。
  - --update：接受新内容并写回 vendor 文件 + 更新 manifest 中的 sha256。
    用于主动升级 vendor 时（修改 manifest 中的 source 版本号后跑一次）。

manifest.json 是单一来源：path、source、version、license、sha256 都从这里读。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Windows runner 默认 cp1252，print 中文（"未变"、"已更新"等）会 UnicodeEncodeError
# 进而 exit 1。与 sync.py 模式一致：在最早机会 reconfigure stdio 为 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_VENDOR = REPO_ROOT / "web" / "vendor"
MANIFEST = WEB_VENDOR / "manifest.json"
TIMEOUT = 30
USER_AGENT = "latest-softwares-vendor-updater"
REQUIRED_ASSET_FIELDS = {"path", "source", "version", "license", "sha256"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _validate_manifest(manifest: dict) -> list[str]:
    errors: list[str] = []
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not assets:
        return ["assets 必须是非空列表"]

    for index, asset in enumerate(assets, start=1):
        if not isinstance(asset, dict):
            errors.append(f"assets[{index}] 必须是对象")
            continue
        missing = sorted(
            field for field in REQUIRED_ASSET_FIELDS if not asset.get(field)
        )
        if missing:
            label = asset.get("path") or f"#{index}"
            errors.append(f"{label}: 缺少或为空字段 {', '.join(missing)}")
    return errors


def _save_manifest(manifest: dict) -> None:
    # 缩进 2 空格 + 末尾换行 —— 与现有格式一致
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _process_asset(asset: dict, *, update: bool) -> tuple[bool, str]:
    """处理单个 asset。返回 (是否成功, 简短状态描述)。"""
    path = REPO_ROOT / "web" / asset["path"]
    source = asset["source"]
    expected = asset.get("sha256", "")

    try:
        data = _download(source)
    except (urllib.error.URLError, TimeoutError) as exc:
        return False, f"下载失败：{exc}"

    actual = _sha256(data)

    if update:
        path.write_bytes(data)
        if actual == expected:
            return True, f"未变（sha256 {actual[:12]}…）"
        asset["sha256"] = actual
        return True, f"已更新 sha256 {expected[:12] or '<空>'}… → {actual[:12]}…"

    # 校验模式
    if actual != expected:
        return False, (
            f"sha256 不匹配！\n      manifest: {expected}\n      实际:     {actual}"
        )
    if not path.exists() or _sha256(path.read_bytes()) != actual:
        return False, "本地文件缺失或与远端不一致"
    return True, f"✓ 校验通过（{len(data)} 字节）"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="下载并写回 vendor 文件 + 更新 manifest 中的 sha256（主动升级）。",
    )
    args = parser.parse_args()

    if not MANIFEST.exists():
        print(f"manifest 不存在：{MANIFEST}", file=sys.stderr)
        return 1

    manifest = _load_manifest()
    errors = _validate_manifest(manifest)
    if errors:
        print("manifest.json 校验失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    failures = 0
    for asset in manifest.get("assets", []):
        ok, status = _process_asset(asset, update=args.update)
        prefix = "  ✓" if ok else "  ✗"
        print(f"{prefix} {asset['path']}: {status}")
        if not ok:
            failures += 1

    if args.update and failures == 0:
        _save_manifest(manifest)
        print("manifest.json 已更新")

    if failures:
        print(f"\n{failures} 个 asset 处理失败", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
