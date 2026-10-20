"""发现状态管理（游标、已拒绝、重试与扫描预算）。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class DiscoveryState:
    version: int = 1
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    cursors: dict[str, Any] = field(
        default_factory=lambda: {
            "github": {"page": 1, "min_stars": 5000},
            "winget": {"partition_index": 0, "cursor": 0},
            "brew": {"cursor": 0},
            "scoop": {"cursor": 0},
        }
    )
    rejected: list[str] = field(default_factory=list)  # 已拒绝候选的 id 或 repo
    pending: list[dict[str, Any]] = field(default_factory=list)
    retries: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )  # ident -> {retry_count, last_error, last_attempt}

    @classmethod
    def load(cls, path: Path | str) -> DiscoveryState:
        """从指定文件加载状态；如果文件不存在或异常，返回初始状态。"""
        p = Path(path)
        if not p.is_file():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return cls()
            cursors = data.get("cursors")
            if not isinstance(cursors, dict):
                cursors = {}
            rejected = data.get("rejected")
            if not isinstance(rejected, list):
                rejected = []
            retries = data.get("retries")
            if not isinstance(retries, dict):
                retries = {}
            return cls(
                version=int(data.get("version", 1)),
                updated_at=str(data.get("updated_at", "")),
                cursors=cursors,
                rejected=[str(x) for x in rejected],
                pending=data.get("pending", []),
                retries=retries,
            )
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid discovery state: {p}") from exc

    def save(self, path: Path | str) -> None:
        """将状态以格式化 JSON 写回文件。"""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        data = {
            "version": self.version,
            "updated_at": self.updated_at,
            "cursors": self.cursors,
            "rejected": self.rejected,
            "pending": self.pending,
            "retries": self.retries,
        }
        temporary = p.with_suffix(p.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, p)

    def is_rejected(self, ident: str) -> bool:
        """检查特定 id 或 repo 是否已被跨轮标记为拒绝。"""
        if not ident:
            return False
        ident_lower = ident.strip().lower()
        return any(str(r).strip().lower() == ident_lower for r in self.rejected)

    def record_retry(self, ident: str, error: str) -> None:
        """记录失败重试记录（暂时网络失败记录，不要永久拒绝）。"""
        if not ident:
            return
        rec = self.retries.get(ident, {"retry_count": 0})
        rec["retry_count"] = rec.get("retry_count", 0) + 1
        rec["last_error"] = str(error)
        rec["last_attempt"] = datetime.now(timezone.utc).isoformat()
        rec["next_attempt"] = (
            datetime.now(timezone.utc)
            + timedelta(hours=min(24, 2 ** min(rec["retry_count"], 4)))
        ).isoformat()
        self.retries[ident] = rec

    def record_success(self, ident: str) -> None:
        """操作成功后清除先前的重试记录。"""
        if ident in self.retries:
            self.retries.pop(ident, None)

    def get_cursor(self, source: str, default: Any = None) -> Any:
        return self.cursors.get(source, default)

    def update_cursor(self, source: str, cursor_value: Any) -> None:
        self.cursors[source] = cursor_value
