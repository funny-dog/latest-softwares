"""发现源统一导出与调度。"""

from __future__ import annotations

from typing import Any, Callable

from ..models import Candidate
from . import brew, github, scoop, winget

AVAILABLE_SOURCES: dict[str, Callable[..., list[Candidate]]] = {
    "github": github.discover,
    "winget": winget.discover,
    "brew": brew.discover,
    "scoop": scoop.discover,
}


def fetch_source(
    name: str,
    *,
    max_scan: int,
    min_stars: int = 5000,
    state: Any = None,
) -> tuple[list[Candidate], str | None]:
    """执行单个发现源的抓取，返回 (candidates, error)。

    保证单源异常隔离，不向外抛出致命异常。
    """
    fn = AVAILABLE_SOURCES.get(name)
    if fn is None:
        return [], f"未知发现源: {name}"

    try:
        if name == "github":
            cands = fn(min_stars=min_stars, max_scan=max_scan, state=state)
            err = getattr(github, "LAST_ERROR", None)
            return cands, err
        elif name == "winget":
            cands = fn(max_scan=max_scan, state=state)
            err = getattr(winget, "LAST_ERROR", None)
            return cands, err
        elif name == "brew":
            cands = fn(max_scan=max_scan, state=state)
            err = getattr(brew, "LAST_ERROR", None)
            return cands, err
        elif name == "scoop":
            cands = fn(max_scan=max_scan, state=state)
            err = getattr(scoop, "LAST_ERROR", None)
            return cands, err
        else:
            return fn(max_scan=max_scan, state=state), None
    except Exception as exc:
        return [], str(exc)
