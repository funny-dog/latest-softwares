"""自动发现热门软件 CLI。

流程：多源发现（GitHub / WinGet / Homebrew / Scoop）→ 统一去重与证据映射
→ 编排过滤（可靠链接+资产匹配+同名歧义冲突判定+佐证）
→ 分类+翻译 → 组装条目（github_release / download_page）
→ 追加写入 packages/<edition>.yaml → 校验
→ 持久化状态（--state-file）与人工审查记录（--review-file）
→ 输出新增 id 列表（供 workflow 用）。

运行：
  python -m scripts.discover         # 包导入方式
  python scripts/discover_popular.py # 脚本方式
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Windows runner 默认 cp1252，输出中文/✓ 会 UnicodeEncodeError；与 sync.py 一致先 reconfigure。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.discover.sources import github, AVAILABLE_SOURCES, fetch_source  # type: ignore
    from scripts.discover.sources.github import discover  # type: ignore
    from scripts.discover.aggregate import select_candidates  # type: ignore
    from scripts.discover.categorize import categorize  # type: ignore
    from scripts.discover.translate import translate_to_zh  # type: ignore
    from scripts.discover.generate import build_entry  # type: ignore
    from scripts.discover.yaml_writer import append_entries  # type: ignore
    from scripts.discover.state import DiscoveryState  # type: ignore
    from scripts.discover.review import ReviewManager  # type: ignore
    from scripts.discover.models import (  # type: ignore
        DEFAULT_MIN_STARS,
        DEFAULT_MAX_OUTPUT,
        DEFAULT_MAX_SCAN,
        DEFAULT_MAX_CORROBORATE,
        DEFAULT_SOURCES,
        DEFAULT_STATE_FILE,
        DEFAULT_REVIEW_FILE,
        Candidate,
    )
    from scripts.config_loader import load_packages_config  # type: ignore
    from scripts.validate_config import validate_config  # type: ignore
else:
    from .discover.sources import github, AVAILABLE_SOURCES, fetch_source
    from .discover.sources.github import discover
    from .discover.aggregate import select_candidates
    from .discover.categorize import categorize
    from .discover.translate import translate_to_zh
    from .discover.generate import build_entry
    from .discover.yaml_writer import append_entries
    from .discover.state import DiscoveryState
    from .discover.review import ReviewManager
    from .discover.models import (
        DEFAULT_MIN_STARS,
        DEFAULT_MAX_OUTPUT,
        DEFAULT_MAX_SCAN,
        DEFAULT_MAX_CORROBORATE,
        DEFAULT_SOURCES,
        DEFAULT_STATE_FILE,
        DEFAULT_REVIEW_FILE,
        Candidate,
    )
    from .config_loader import load_packages_config
    from .validate_config import validate_config

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "packages" / "shared.yaml"


def _parse_sources(raw: list[str] | None) -> list[str]:
    """解析 CLI --sources 参数，支持逗号或空格分隔。"""
    if not raw:
        return list(DEFAULT_SOURCES)
    res: list[str] = []
    for item in raw:
        for part in item.replace(",", " ").split():
            clean = part.strip().lower()
            if clean:
                res.append(clean)
    return res or list(DEFAULT_SOURCES)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-stars", type=int, default=DEFAULT_MIN_STARS)
    parser.add_argument("--max-output", type=int, default=DEFAULT_MAX_OUTPUT)
    parser.add_argument("--max-scan", type=int, default=DEFAULT_MAX_SCAN)
    parser.add_argument("--max-corroborate", type=int, default=DEFAULT_MAX_CORROBORATE)
    parser.add_argument(
        "--sources",
        nargs="*",
        default=DEFAULT_SOURCES,
        help="指定发现源列表（如 github winget brew scoop），默认仅 github",
    )
    parser.add_argument(
        "--state-file",
        default=str(REPO_ROOT / DEFAULT_STATE_FILE),
        help="状态文件路径，记录游标、重试与跨轮拒绝名单",
    )
    parser.add_argument(
        "--review-file",
        default=str(REPO_ROOT / DEFAULT_REVIEW_FILE),
        help="人工审查候选文件路径，记录冲突与无可靠链接项",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--new-ids-file", default=str(REPO_ROOT / "discover_new_ids.txt")
    )
    # argv 为 None 时 argparse 自动读 sys.argv[1:]；测试传显式列表。
    args = parser.parse_args(argv)

    state = DiscoveryState.load(args.state_file)
    review_manager = ReviewManager()
    selected_sources = list(dict.fromkeys(_parse_sources(args.sources)))
    if set(selected_sources) - AVAILABLE_SOURCES.keys():
        parser.error("unknown discovery source")
    if args.max_scan < 1 or args.max_output < 1 or args.max_corroborate < 0:
        parser.error("invalid scan/output/corroboration budget")
    rejections = REPO_ROOT / "config/discovery-rejections.json"
    if rejections.exists():
        import json

        state.rejected = json.loads(rejections.read_text(encoding="utf-8"))["rejected"]

    all_candidates: list[Candidate] = [Candidate(**value) for value in state.pending]
    failed_sources: dict[str, str] = {}
    successful_sources: list[str] = []

    for src in selected_sources:
        if src not in AVAILABLE_SOURCES:
            print(f"⚠ 未知发现源: {src}，跳过", file=sys.stderr)
            continue

        cands: list[Candidate] = []
        err: str | None = None
        if src == "github":
            try:
                cands = discover(
                    min_stars=args.min_stars,
                    max_scan=args.max_scan,
                    state=state,
                )
                err = getattr(github, "LAST_ERROR", None)
            except Exception as exc:
                err = str(exc)
                cands = []
        else:
            cands, err = fetch_source(
                src,
                max_scan=args.max_scan,
                min_stars=args.min_stars,
                state=state,
            )

        if err:
            print(f"⚠ 发现源 '{src}' 抓取异常: {err}", file=sys.stderr)
            failed_sources[src] = err
        else:
            successful_sources.append(src)

        all_candidates.extend(cands)
        print(f"源 [{src}] 发现 {len(cands)} 个候选")

    # 网络失败单源隔离但不能伪装成成功零结果；全源失败返回非零。
    if failed_sources and not successful_sources and not all_candidates:
        print("❌ 所有选定的发现源均失败，退出", file=sys.stderr)
        state.save(args.state_file)
        review_manager.save(args.review_file)
        return 1

    print(f"汇总多源候选共 {len(all_candidates)} 个")

    selected = select_candidates(
        all_candidates,
        max_output=args.max_output,
        max_corroborate=args.max_corroborate,
        review_manager=review_manager,
        state=state,
    )

    print(f"过滤后保留 {len(selected)} 个候选")

    entries: list[dict] = []
    new_ids: list[str] = []
    seen_ids: set[str] = set()

    for cand, pattern in selected:
        fetcher_type = cand.fetcher or (
            "github_release" if (cand.repo and pattern) else "download_page"
        )
        source_ids = cand.manifest_ids()
        family = cand.platform.split("-")[0]
        providers = (
            ["brew"]
            if family == "mac"
            else ["winget", "scoop"]
            if family == "win"
            else []
        )
        provider = next((p for p in providers if p in source_ids), "")
        if provider and cand.download_url:
            fetcher_type = "package_manifest"
        entry = build_entry(
            provider=provider,
            package=source_ids.get(provider, ""),
            name=cand.name,
            category=categorize(cand.topics, cand.description),
            repo=cand.repo,
            pattern=pattern,
            desc_en=cand.description,
            desc_cn=translate_to_zh(cand.description),
            fetcher=fetcher_type,
            homepage=cand.homepage,
            download_url=cand.download_url,
            platform=cand.platform or "win-x64",
            link_kind=cand.link_kind,
        )
        if source_ids:
            entry["source_ids"] = source_ids
        entry_errors = validate_config({"packages": [entry]})
        if entry_errors:
            review_manager.add(
                id=entry["id"],
                name=cand.name,
                reason="no_reliable_link",
                detail="; ".join(entry_errors),
                sources=cand.sources,
                candidates=[cand],
            )
            continue
        entry_id = entry["id"]
        # 跳过空 id 或批内重复 id：单个异常名不应让整轮校验失败而丢掉其它好候选。
        if not entry_id:
            print(
                f"⚠ 跳过 {cand.name}：名称无法生成合法 id",
                file=sys.stderr,
            )
            review_manager.add(
                id=entry_id or "invalid",
                name=cand.name,
                reason="skipped",
                detail="无法生成合法 id",
                sources=cand.sources,
                candidates=[cand],
            )
            continue
        if entry_id in seen_ids:
            print(
                f"⚠ 跳过 {cand.name}：id {entry_id!r} 与本批其它候选冲突",
                file=sys.stderr,
            )
            review_manager.add(
                id=entry_id,
                name=cand.name,
                reason="conflict",
                detail=f"id '{entry_id}' 与本批其它候选冲突",
                sources=cand.sources,
                candidates=[cand],
            )
            continue
        seen_ids.add(entry_id)
        review_manager.add(
            id=entry_id,
            name=cand.name,
            reason="selected",
            detail="Pending human review; download is not yet verified",
            sources=cand.sources,
            candidates=[cand],
        )
        entries.append(entry)
        new_ids.append(entry_id)
        tag = pattern if pattern else f"url:{cand.download_url}"
        print(f"✓ {entry_id} [{fetcher_type}]: {cand.name} → {tag}")

    output_path = Path(args.output)
    if entries:
        import yaml

        existing = (
            yaml.safe_load(output_path.read_text(encoding="utf-8"))
            if output_path.exists()
            else {"packages": []}
        )
        cfg = (
            load_packages_config()
            if output_path.resolve() == DEFAULT_OUTPUT.resolve()
            else existing
        )
        errors = validate_config({"packages": cfg.get("packages", []) + entries})
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            state.save(args.state_file)
            review_manager.save(args.review_file)
            return 1
        append_entries(entries, output_path)

    # 持久化状态、审查记录与新 ID 列表
    state.save(args.state_file)
    review_manager.save(args.review_file)
    Path(args.new_ids_file).write_text("\n".join(new_ids), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
