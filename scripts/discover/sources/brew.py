"""发现源：Homebrew Cask 官方 JSON API。

通过 formulae.brew.sh/api/cask.json 读取结构化元数据，不执行任何 Ruby 代码。
支持非 Windows 候选（如 macOS 软件），提供下载与主页证据。
"""

from __future__ import annotations

from typing import Any

from ...net import get_json
from ..models import DEFAULT_MAX_SCAN, Candidate
from ..url_utils import is_valid_http_url, extract_github_repo

_BREW_API = "https://formulae.brew.sh/api/cask.json"
_TIMEOUT = 30

LAST_ERROR: str | None = None


def infer_brew_platform(url: str, cask_data: dict[str, Any]) -> tuple[str, str | None]:
    """根据 url 和 cask 元数据中的明确架构证据推断平台。

    只有当有明确证据时才标注具体架构（mac-arm64, mac-x64, mac-universal）；
    若无明确证据，使用不含架构的 'mac' 平台。
    """
    url_lower = url.lower()
    if any(k in url_lower for k in ("universal", "all-arch")):
        return "mac-universal", "direct"
    if any(k in url_lower for k in ("arm64", "aarch64", "apple-silicon")):
        return "mac-arm64", "direct"
    if any(k in url_lower for k in ("x86_64", "x64", "intel")):
        return "mac-x64", "direct"

    # 无明确架构证据：使用不含架构的 'mac' 平台，入口类型仍按响应地址记录
    return "mac", "direct"


def discover(
    max_scan: int = DEFAULT_MAX_SCAN,
    *,
    cursor: int = 0,
    state: Any = None,
) -> list[Candidate]:
    """通过 Homebrew Cask JSON API 发现软件。

    使用 cursor 游标进行有界增量扫描，防止每轮重复前 100 项。
    """
    global LAST_ERROR
    LAST_ERROR = None
    candidates: list[Candidate] = []

    cur = cursor
    if state and hasattr(state, "get_cursor"):
        cdata = state.get_cursor("brew")
        if isinstance(cdata, dict):
            cur = int(cdata.get("cursor", cur))
        elif isinstance(cdata, int):
            cur = cdata

    try:
        data = get_json(_BREW_API, timeout=_TIMEOUT)
    except Exception as exc:
        LAST_ERROR = str(exc)
        if state and hasattr(state, "record_retry"):
            state.record_retry("brew:api:cask.json", str(exc))
        return candidates

    if not isinstance(data, list):
        return candidates

    total = len(data)
    if total == 0:
        return candidates

    scanned = 0
    idx = cur % total

    while scanned < max_scan and scanned < total:
        cask = data[idx]
        idx = (idx + 1) % total
        scanned += 1

        if not isinstance(cask, dict):
            continue

        if cask.get("disabled"):
            continue

        token = str(cask.get("token") or "").strip()
        if not token:
            continue

        raw_name = cask.get("name")
        name = ""
        if isinstance(raw_name, list) and raw_name:
            name = str(raw_name[0])
        elif isinstance(raw_name, str):
            name = raw_name
        if not name:
            name = token.replace("-", " ").title()

        homepage = str(cask.get("homepage") or "").strip()
        url = str(cask.get("url") or "").strip()
        desc = str(cask.get("desc") or "").strip()

        # 检查取得的 url 是 http(s)，拒绝脚本或不支持的条件地址
        download_url = url if is_valid_http_url(url) else ""
        repo = extract_github_repo(homepage) or extract_github_repo(download_url) or ""

        platform, link_kind = infer_brew_platform(download_url, cask)

        cand = Candidate(
            repo=repo,
            name=name,
            stars=0,
            description=desc,
            homepage_url=homepage,
            download_url=download_url,
            source="brew",
            sources=["brew"],
            external_id=f"brew:{token}",
            platform=platform,
            link_kind=link_kind,
            fetcher="github_release" if repo else "download_page",
            evidences=[
                {
                    "source": "brew",
                    "external_id": token,
                    "url": download_url,
                    "homepage": homepage,
                }
            ],
        )
        candidates.append(cand)

    if state and hasattr(state, "update_cursor"):
        state.update_cursor("brew", {"cursor": idx, "scanned": scanned})

    return candidates
