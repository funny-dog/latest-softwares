"""发现源：Scoop bucket JSON（Main / Extras 仓库）。

通过 GitHub contents / raw JSON 获取结构化元数据，不执行任何 PowerShell 脚本。
"""

from __future__ import annotations

from typing import Any

from ...net import get_json, github_headers
from ..models import DEFAULT_MAX_SCAN, Candidate
from ..url_utils import is_valid_http_url, extract_github_repo

_GITHUB_API = "https://api.github.com"
_SCOOP_BUCKETS = ["ScoopInstaller/Main", "ScoopInstaller/Extras"]
_TIMEOUT = 30

LAST_ERROR: str | None = None


def _select_download(data: dict[str, Any]) -> tuple[str, str]:
    for key, platform in (
        ("64bit", "win-x64"),
        ("arm64", "win-arm64"),
        ("32bit", "win-x86"),
        (None, "win"),
    ):
        spec = data.get("architecture", {}).get(key, {}) if key else data
        url = spec.get("url")
        if isinstance(url, list):
            url = url[0] if len(url) == 1 else None
        if is_valid_http_url(url):
            return str(url), platform
    return "", "win"


def extract_scoop_download_url(data: dict[str, Any]) -> str:
    return _select_download(data)[0]


def discover(
    max_scan: int = DEFAULT_MAX_SCAN,
    *,
    cursor: int = 0,
    bucket_index: int = 0,
    state: Any = None,
) -> list[Candidate]:
    """有界扫描 Scoop bucket 中的应用 manifest。"""
    global LAST_ERROR
    LAST_ERROR = None
    candidates: list[Candidate] = []

    b_idx = bucket_index % len(_SCOOP_BUCKETS)
    cur = cursor

    if state and hasattr(state, "get_cursor"):
        cdata = state.get_cursor("scoop")
        if isinstance(cdata, dict):
            b_idx = int(cdata.get("bucket_index", b_idx)) % len(_SCOOP_BUCKETS)
            cur = int(cdata.get("cursor", cur))

    repo = _SCOOP_BUCKETS[b_idx]
    url = f"{_GITHUB_API}/repos/{repo}/git/trees/master?recursive=1"
    try:
        tree = get_json(url, headers=github_headers(), timeout=_TIMEOUT)
        if not isinstance(tree, dict) or tree.get("truncated"):
            raise ValueError("Scoop tree is incomplete")
        items = [
            {
                "name": item["path"].split("/")[-1],
                "download_url": f"https://raw.githubusercontent.com/{repo}/master/{item['path']}",
            }
            for item in tree.get("tree", [])
            if item.get("type") == "blob"
            and item["path"].startswith("bucket/")
            and item["path"].endswith(".json")
        ]
        items.sort(key=lambda item: item["name"])
    except Exception as exc:
        LAST_ERROR = str(exc)
        if state and hasattr(state, "record_retry"):
            state.record_retry(f"scoop:bucket:{repo}", str(exc))
        return candidates

    if not isinstance(items, list):
        return candidates

    total_items = len(items)
    if total_items == 0:
        return candidates

    scanned = 0
    i = cur % total_items

    while scanned < max_scan and scanned < total_items:
        item = items[i]
        i = (i + 1) % total_items
        scanned += 1

        if not isinstance(item, dict) or not str(item.get("name", "")).endswith(
            ".json"
        ):
            continue

        raw_url = item.get("download_url")
        if not raw_url:
            continue

        try:
            data = get_json(raw_url, timeout=_TIMEOUT)
        except Exception as exc:
            LAST_ERROR = str(exc)
            i = (i - 1) % total_items
            if state:
                state.record_retry(f"scoop:{repo}:{item['name']}", str(exc))
            break

        if not isinstance(data, dict):
            continue

        app_name = item.get("name", "").replace(".json", "")
        homepage = str(data.get("homepage") or "").strip()
        desc = str(data.get("description") or "").strip()
        download_url, platform = _select_download(data)

        repo_ident = (
            extract_github_repo(homepage) or extract_github_repo(download_url) or ""
        )

        cand = Candidate(
            repo=repo_ident,
            name=app_name,
            stars=0,
            description=desc,
            homepage_url=homepage,
            download_url=download_url,
            source="scoop",
            sources=["scoop"],
            external_id=f"scoop:{repo.split('/')[-1].lower()}/{app_name}",
            platform=platform,
            link_kind="direct",
            fetcher="github_release" if repo_ident else "download_page",
            evidences=[
                {
                    "source": "scoop",
                    "bucket": repo,
                    "external_id": app_name,
                    "url": download_url,
                    "homepage": homepage,
                }
            ],
        )
        candidates.append(cand)

    if state and hasattr(state, "update_cursor"):
        state.update_cursor(
            "scoop",
            {
                "bucket_index": b_idx if i > cur else (b_idx + 1) % len(_SCOOP_BUCKETS),
                "cursor": i if i > cur else 0,
                "scanned": scanned,
            },
        )

    return candidates
