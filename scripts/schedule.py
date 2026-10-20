"""同步优先级和失败退避；调度状态随软件记录进入下一轮快照。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

from app_core.downloads import parse_time


def _fingerprint(entry: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            {key: entry.get(key) for key in ("fetcher", "args", "homepage")},
            sort_keys=True,
        ).encode()
    ).hexdigest()


def next_sync(entry: dict[str, Any], failures: int = 0) -> dict[str, Any]:
    hours = {"critical": 6, "standard": 24, "long_tail": 72}.get(
        entry.get("priority", "standard"), 24
    )
    if entry.get("fetcher") == "download_page":
        hours = 72
    if failures:
        hours = min(24, 2 ** min(failures, 4))
    return {
        "failures": failures,
        "fingerprint": _fingerprint(entry),
        "next_attempt_at": (
            datetime.now(timezone.utc) + timedelta(hours=hours)
        ).isoformat(timespec="seconds"),
    }


def sync_due(previous: dict[str, Any], entry: dict[str, Any] | None = None) -> bool:
    if entry is not None and previous.get("_sync", {}).get(
        "fingerprint"
    ) != _fingerprint(entry):
        return True
    next_at = parse_time(previous.get("_sync", {}).get("next_attempt_at"))
    return next_at is None or next_at <= datetime.now(timezone.utc)
