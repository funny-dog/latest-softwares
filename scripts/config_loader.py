"""共享的 packages 配置加载逻辑。

支持从 packages/ 目录加载多个 yaml 文件并合并，
也兼容旧的单文件 packages.yaml（回退路径）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_FILE = REPO_ROOT / "packages.yaml"
PACKAGES_DIR = REPO_ROOT / "packages"


def _load_packages_dir(packages_dir: Path) -> dict[str, Any]:
    """从 packages/ 目录加载并合并所有 yaml 文件"""
    all_packages: list[dict[str, Any]] = []
    for yaml_file in sorted(packages_dir.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        all_packages.extend(data.get("packages", []))
    return {"packages": all_packages}


def load_packages_config() -> dict[str, Any]:
    """加载软件包配置，优先从 packages/ 目录加载，回退到单文件"""
    if PACKAGES_DIR.is_dir():
        return _load_packages_dir(PACKAGES_DIR)
    else:
        return yaml.safe_load(PACKAGES_FILE.read_text(encoding="utf-8"))
