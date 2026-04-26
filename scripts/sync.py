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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

# Windows runner 默认用 cp1252，输出 ✓/✗/中文会 UnicodeEncodeError 进而崩掉整个脚本。
# 在最早机会重置 stdout/stderr 为 UTF-8，保证后续所有 print 安全。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# 兼容两种运行方式：作为模块（python -m scripts.sync）或作为脚本（python scripts/sync.py）
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.fetchers import FETCHERS, FetchResult  # type: ignore
else:
    from .fetchers import FETCHERS, FetchResult


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_FILE = REPO_ROOT / "packages.yaml"
DATA_FILE = REPO_ROOT / "data" / "latest.json"
MAX_WORKERS = 10  # API 请求 I/O 密集型，10-15 线程可获得最佳吞吐


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


def _sync_one(entry: dict, previous: dict[str, dict]) -> tuple[int, dict | None, bool, tuple[str, str] | None]:
    """运行单个 fetcher，返回 (index, result_dict, ok, error_info)。

    此函数由 ThreadPoolExecutor 并发调用，只读 previous，无副作用。
    """
    eid = entry["id"]
    fetcher_name = entry["fetcher"]
    fetcher = FETCHERS.get(fetcher_name)

    if fetcher is None:
        msg = f"未知 fetcher: {fetcher_name}"
        print(f"✗ {eid}: {msg}", file=sys.stderr)
        if eid in previous:
            stale = dict(previous[eid])
            stale["_stale"] = True
            return (eid, stale, False, (eid, msg))
        return (eid, None, False, (eid, msg))

    try:
        res: FetchResult = fetcher(entry.get("args", {}))
        res.id = eid
        res.name = entry.get("name", res.name)
        res.category = entry.get("category", res.category)
        res.homepage = entry.get("homepage", res.homepage)
        result = res.to_dict()
        print(f"✓ {eid}: {res.version} ({len(res.assets)} 个平台)")
        return (eid, result, True, None)
    except Exception as e:
        msg = str(e)
        print(f"✗ {eid}: {msg}", file=sys.stderr)
        if eid in previous:
            stale = dict(previous[eid])
            stale["_stale"] = True
            print(f"  ↳ 复用上次数据（{previous[eid].get('version')}）", file=sys.stderr)
            return (eid, stale, False, (eid, msg))
        return (eid, None, False, (eid, msg))


def main() -> int:
    cfg = yaml.safe_load(PACKAGES_FILE.read_text(encoding="utf-8"))
    entries = cfg.get("packages", [])
    if not entries:
        print("packages.yaml 没有配置任何软件", file=sys.stderr)
        return 1

    previous = load_previous()
    total = len(entries)
    success = 0
    failures: list[tuple[str, str]] = []

    # 保存 entries 的有序结果，按 index 重建（因为 as_completed 无序）
    result_map: dict[str, dict] = {}
    # entries 的位置 → id 的有序映射
    order: list[str] = [e["id"] for e in entries]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_sync_one, entry, previous): entry
            for entry in entries
        }
        for future in as_completed(futures):
            entry = futures[future]
            eid, result, ok, error_info = future.result()
            idx = order.index(eid)
            if result is not None:
                result_map[eid] = result
            if ok:
                success += 1
            elif error_info:
                failures.append(error_info)

    # 按 packages.yaml 顺序重建结果列表
    results = [result_map[eid] for eid in order if eid in result_map]

    # 写出
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "schema_version": 1,
        "packages": results,
        "stats": {
            "total": total,
            "success": success,
            "failed": len(failures),
        },
    }
    DATA_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"\n写入 {DATA_FILE.relative_to(REPO_ROOT)}：成功 {success}/{total}")

    return 0 if success > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
