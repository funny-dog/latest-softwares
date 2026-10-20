"""GitHub 发现：持久化页内游标，按星数分窗避开 Search 的 1000 条结果上限。"""

from __future__ import annotations

from datetime import datetime, timezone

from ...net import get_json, github_headers
from ..models import DEFAULT_MIN_STARS, DEFAULT_MAX_SCAN, Candidate
from ..state import DiscoveryState

_GITHUB_API = "https://api.github.com"
_TIMEOUT = 30
_PER_PAGE = 50
LAST_ERROR: str | None = None


def _latest_release(repo: str) -> dict | None:
    try:
        return get_json(
            f"{_GITHUB_API}/repos/{repo}/releases/latest",
            headers=github_headers(),
            timeout=_TIMEOUT,
        )
    except Exception as exc:
        if getattr(getattr(exc, "response", None), "status_code", None) == 404:
            return None
        raise


def discover(
    min_stars: int = DEFAULT_MIN_STARS,
    max_scan: int = DEFAULT_MAX_SCAN,
    *,
    page_cursor: int = 1,
    state: DiscoveryState | None = None,
) -> list[Candidate]:
    global LAST_ERROR
    LAST_ERROR = None
    saved = state.get_cursor("github", {}) if state else {}
    ranges = saved.get("ranges") if saved.get("min_stars") == min_stars else None
    ranges = ranges or [
        {"min": min_stars, "max": None, "page": page_cursor, "offset": 0}
    ]
    candidates = []
    scanned = 0

    def fetch_item(item: dict) -> None:
        nonlocal scanned
        global LAST_ERROR
        scanned += 1
        repo = item.get("full_name")
        if not repo:
            return
        key = f"github:repo:{repo}"
        try:
            release = _latest_release(repo)
        except Exception as exc:
            LAST_ERROR = str(exc)
            if state:
                state.record_retry(key, str(exc))
                state.retries[key]["item"] = item
            return
        if state:
            state.record_success(key)
        names = [a["name"] for a in (release or {}).get("assets", []) if a.get("name")]
        if not names:
            return
        candidates.append(
            Candidate(
                repo=repo,
                name=item.get("name") or repo.split("/")[-1],
                stars=int(item.get("stargazers_count", 0)),
                description=item.get("description") or "",
                topics=list(item.get("topics") or []),
                asset_names=names,
                released_at=release.get("published_at"),
                homepage_url=item.get("homepage") or "",
            )
        )

    if state:
        for key, retry in list(state.retries.items()):
            if scanned >= min(10, max_scan):
                break
            if (
                key.startswith("github:repo:")
                and retry.get("item")
                and retry.get("next_attempt", "")
                <= datetime.now(timezone.utc).isoformat()
            ):
                fetch_item(retry["item"])
    search_budget = 12
    while ranges and scanned < max_scan and search_budget:
        scope = ranges[-1]
        search_budget -= 1
        stars = (
            f">={scope['min']}"
            if scope["max"] is None
            else f"{scope['min']}..{scope['max']}"
        )
        url = f"{_GITHUB_API}/search/repositories?q=stars:{stars}&sort=stars&order=desc&per_page={_PER_PAGE}&page={scope['page']}"
        try:
            result = get_json(url, headers=github_headers(), timeout=_TIMEOUT)
            if not isinstance(result, dict) or result.get("incomplete_results"):
                raise ValueError("incomplete GitHub search response")
            items = result.get("items", [])
            if result.get("total_count", 0) > 1000:
                upper = scope["max"] or (
                    items[0]["stargazers_count"] if items else scope["min"]
                )
                if upper <= scope["min"]:
                    # shortcut: 同一星数超过1000仓库时暂停该分窗，需按创建时间进一步分区。
                    raise ValueError(
                        "GitHub star cohort exceeds 1000 results; finer partition required"
                    )
                middle = (upper + scope["min"]) // 2
                ranges[-1:] = [
                    {"min": scope["min"], "max": middle, "page": 1, "offset": 0},
                    {"min": middle + 1, "max": upper, "page": 1, "offset": 0},
                ]
                continue
            while scope["offset"] < len(items) and scanned < max_scan:
                fetch_item(items[scope["offset"]])
                scope["offset"] += 1
            if scope["offset"] == len(items):
                if len(items) < _PER_PAGE or (
                    result.get("total_count")
                    and scope["page"] * _PER_PAGE >= result["total_count"]
                ):
                    ranges.pop()
                else:
                    scope["page"] += 1
                    scope["offset"] = 0
        except Exception as exc:
            LAST_ERROR = str(exc)
            if state:
                state.record_retry("github:search", str(exc))
            break
    if state:
        state.update_cursor("github", {"ranges": ranges, "min_stars": min_stars})
        if not LAST_ERROR:
            state.record_success("github:search")
    return candidates
