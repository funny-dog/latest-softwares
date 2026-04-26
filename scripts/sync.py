"""主同步入口。

读 packages.yaml → 派发到 fetcher → 汇总写入 data/latest.json。

设计原则：
  - 单个 fetcher 失败不中断流程（其它软件继续）
  - 失败的软件复用上一次 latest.json 中的旧数据，README 中由 _stale 字段标记
  - 退出码：全部失败时为 1，部分失败为 0（CI 仍认为成功，但可在日志看到 ✗）

运行方式：
  python -m scripts.sync         # 推荐（包导入）
  或在仓库根目录：
  python scripts/sync.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

# 兼容两种运行方式：作为模块（python -m scripts.sync）或作为脚本（python scripts/sync.py）
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.fetchers import FETCHERS, FetchResult  # type: ignore
else:
    from .fetchers import FETCHERS, FetchResult


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_FILE = REPO_ROOT / "packages.yaml"
DATA_FILE = REPO_ROOT / "data" / "latest.json"


def load_previous() -> dict[str, dict]:
    """读上一次的 latest.json，返回 id -> entry 的映射。"""
    if not DATA_FILE.exists():
        return {}
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        return {entry["id"]: entry for entry in data.get("packages", [])}
    except Exception as e:
        print(f"⚠ 无法读取旧数据 {DATA_FILE}: {e}", file=sys.stderr)
        return {}


def main() -> int:
    cfg = yaml.safe_load(PACKAGES_FILE.read_text(encoding="utf-8"))
    entries = cfg.get("packages", [])
    if not entries:
        print("packages.yaml 没有配置任何软件", file=sys.stderr)
        return 1

    previous = load_previous()
    results: list[dict] = []
    success = 0
    failures: list[tuple[str, str]] = []

    for entry in entries:
        eid = entry["id"]
        fetcher_name = entry["fetcher"]
        fetcher = FETCHERS.get(fetcher_name)

        if fetcher is None:
            failures.append((eid, f"未知 fetcher: {fetcher_name}"))
            print(f"✗ {eid}: 未知 fetcher {fetcher_name}", file=sys.stderr)
            if eid in previous:
                stale = dict(previous[eid])
                stale["_stale"] = True
                results.append(stale)
            continue

        try:
            res: FetchResult = fetcher(entry.get("args", {}))
            res.id = eid
            res.name = entry.get("name", res.name)
            res.category = entry.get("category", res.category)
            res.homepage = entry.get("homepage", res.homepage)
            results.append(res.to_dict())
            success += 1
            print(f"✓ {eid}: {res.version} ({len(res.assets)} 个平台)")
        except Exception as e:
            failures.append((eid, str(e)))
            print(f"✗ {eid}: {e}", file=sys.stderr)
            if eid in previous:
                stale = dict(previous[eid])
                stale["_stale"] = True
                results.append(stale)
                print(f"  ↳ 复用上次数据（{previous[eid].get('version')}）", file=sys.stderr)

    # 写出
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "schema_version": 1,
        "packages": results,
        "stats": {
            "total": len(entries),
            "success": success,
            "failed": len(failures),
        },
    }
    DATA_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"\n写入 {DATA_FILE.relative_to(REPO_ROOT)}：成功 {success}/{len(entries)}")

    return 0 if success > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
