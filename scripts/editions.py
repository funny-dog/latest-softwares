"""版本 (edition) 过滤工具 —— 已下沉到 app_core.editions。

逻辑现位于 app_core/editions.py(作为两版 API 共享内核的一部分,且不依赖
scripts/)。本模块保留为向后兼容的 re-export,既有 `from scripts.editions
import ...`(build_web / sync / validate_config / 测试等)无需改动。
"""

from __future__ import annotations

from app_core.editions import (
    DEFAULT_EDITIONS,
    VALID_EDITIONS,
    filter_by_edition,
    filter_data_by_edition,
    get_editions,
    validate_editions,
)

__all__ = [
    "DEFAULT_EDITIONS",
    "VALID_EDITIONS",
    "filter_by_edition",
    "filter_data_by_edition",
    "get_editions",
    "validate_editions",
]
