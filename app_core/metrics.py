"""指标(metrics)的共享工具:时间戳、空指标骨架、包数据加载。

这些是两版后端完全相同的纯函数,与具体存储后端无关。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    """UTC 时间戳(秒精度 ISO 格式),用作 metrics.updated_at。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_metrics(scope: str, storage: str) -> dict[str, Any]:
    """返回一份空的 metrics 骨架。

    scope/storage 由各存储后端提供,如实反映「统计范围」与「存储介质」:
      - 国内版 JSON 文件: instance-local / persistent-file
      - 国际版本地 SQLite: instance-local / local-sqlite
      - 国际版远程 Turso : global / turso-libsql
    """
    return {
        "schema_version": 1,
        "scope": scope,
        "storage": storage,
        "updated_at": None,
        "visits": {"total": 0, "paths": {}},
        "downloads": {"total": 0, "packages": {}, "platforms": {}, "assets": {}},
    }


def load_data(data_file: Path) -> dict[str, Any]:
    """加载 latest.json,文件不存在时返回空结构。"""
    data_file = Path(data_file)
    if data_file.exists():
        return json.loads(data_file.read_text(encoding="utf-8"))
    return {"schema_version": 2, "packages": [], "stats": {}}
