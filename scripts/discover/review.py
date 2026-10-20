"""候选审查记录与输出（提供给人工核验冲突、无可靠链接、跳过等）。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ReviewEntry:
    id: str
    name: str
    reason: str  # "conflict", "no_reliable_link", "skipped", "rejected"
    detail: str
    sources: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "reason": self.reason,
            "detail": self.detail,
            "sources": self.sources,
            "candidates": self.candidates,
        }


class ReviewManager:
    """管理未被自动生成的候选，输出到 review-file 供人工审计。"""

    def __init__(self) -> None:
        self.entries: list[ReviewEntry] = []

    def add(
        self,
        *,
        id: str,
        name: str,
        reason: str,
        detail: str,
        sources: list[str] | None = None,
        candidates: list[Any] | None = None,
    ) -> None:
        cand_dicts: list[dict[str, Any]] = []
        if candidates:
            for c in candidates:
                if hasattr(c, "to_dict"):
                    cand_dicts.append(c.to_dict())
                elif isinstance(c, dict):
                    cand_dicts.append(c)
                else:
                    cand_dicts.append({"raw": str(c)})
        self.entries.append(
            ReviewEntry(
                id=id,
                name=name,
                reason=reason,
                detail=detail,
                sources=list(sources or []),
                candidates=cand_dicts,
            )
        )

    def save(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        conflicts = sum(1 for e in self.entries if e.reason == "conflict")
        no_links = sum(1 for e in self.entries if e.reason == "no_reliable_link")
        skipped = sum(1 for e in self.entries if e.reason in {"skipped", "rejected"})
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_reviewed": len(self.entries),
                "conflicts": conflicts,
                "no_reliable_link": no_links,
                "skipped": skipped,
            },
            "candidates": [e.to_dict() for e in self.entries],
        }
        temporary = p.with_suffix(p.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, p)
