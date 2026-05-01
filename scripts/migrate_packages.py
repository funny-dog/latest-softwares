"""将 packages.yaml 按 editions 字段拆分为 3 个文件"""

import yaml
import sys
from pathlib import Path


def migrate_packages(source: Path, target_dir: Path) -> dict[str, int]:
    """
    迁移 packages.yaml 到按版本拆分的目录

    Args:
        source: 源 packages.yaml 文件路径
        target_dir: 目标目录路径

    Returns:
        各文件的软件数量统计
    """
    with open(source, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    packages = data.get("packages", [])

    # 按 editions 分组
    shared = []
    cn_only = []
    intl_only = []

    for pkg in packages:
        editions = pkg.get("editions", [])
        if "cn" in editions and "intl" in editions:
            shared.append(pkg)
        elif "cn" in editions:
            cn_only.append(pkg)
        elif "intl" in editions:
            intl_only.append(pkg)
        else:
            # 默认归入 shared
            shared.append(pkg)

    # 创建目标目录
    target_dir.mkdir(parents=True, exist_ok=True)

    # 写入文件
    for filename, items in [
        ("shared.yaml", shared),
        ("cn.yaml", cn_only),
        ("intl.yaml", intl_only),
    ]:
        target_file = target_dir / filename
        with open(target_file, "w", encoding="utf-8") as f:
            yaml.dump(
                {"packages": items},
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

    return {
        "shared": len(shared),
        "cn": len(cn_only),
        "intl": len(intl_only),
        "total": len(packages),
    }


def main() -> int:
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("packages.yaml"),
        help="源 packages.yaml 文件路径",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path("packages"),
        help="目标目录路径",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅显示统计信息，不实际写入文件",
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"✗ 源文件不存在: {args.source}", file=sys.stderr)
        return 1

    if args.dry_run:
        with open(args.source, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        packages = data.get("packages", [])
        shared = sum(1 for p in packages if "cn" in p.get("editions", []) and "intl" in p.get("editions", []))
        cn = sum(1 for p in packages if "cn" in p.get("editions", []) and "intl" not in p.get("editions", []))
        intl = sum(1 for p in packages if "intl" in p.get("editions", []) and "cn" not in p.get("editions", []))
        print(f"统计: shared={shared}, cn={cn}, intl={intl}, total={len(packages)}")
        return 0

    stats = migrate_packages(args.source, args.target_dir)
    print(f"✓ 迁移完成:")
    print(f"  shared: {stats['shared']}")
    print(f"  cn: {stats['cn']}")
    print(f"  intl: {stats['intl']}")
    print(f"  total: {stats['total']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
