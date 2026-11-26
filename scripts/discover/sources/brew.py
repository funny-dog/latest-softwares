"""发现源：Homebrew Cask 官方 JSON API 与 30 天安装量 Analytics。

通过 formulae.brew.sh/api/cask.json 与 analytics/cask-install/30d.json 读取结构化元数据，
不执行任何 Ruby 代码。支持非 Windows 候选（如 macOS 软件），提供下载与主页证据。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Any

from ...net import get_json
from ..dedup import (
    existing_homepages,
    existing_ids,
    existing_repos,
    existing_source_ids,
)
from ..generate import slugify
from ..models import DEFAULT_MAX_SCAN, Candidate
from ..url_utils import extract_github_repo, is_valid_http_url, normalize_homepage

_BREW_API = "https://formulae.brew.sh/api/cask.json"
_BREW_ANALYTICS_API = "https://formulae.brew.sh/api/analytics/cask-install/30d.json"
_BREW_CASK_API = "https://formulae.brew.sh/api/cask/{token}.json"
_TIMEOUT = 30

LAST_ERROR: str | None = None

_BREW_CATALOG_LOCK = threading.Lock()
_BREW_CATALOG_CACHE: list[dict[str, Any]] | None = None


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


def _parse_install_count(raw: Any) -> int:
    if isinstance(raw, int):
        return max(0, raw)
    if isinstance(raw, str):
        cleaned = raw.replace(",", "").strip()
        if cleaned.isdigit():
            return int(cleaned)
    return 0


def _cask_to_candidate(
    cask: dict[str, Any], *, installs_30d: int = 0
) -> Candidate | None:
    if not isinstance(cask, dict):
        return None
    if cask.get("disabled"):
        return None

    token = str(cask.get("token") or "").strip()
    if not token:
        return None

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
    evidence: dict[str, Any] = {
        "source": "brew",
        "external_id": token,
        "url": download_url,
        "homepage": homepage,
    }
    if installs_30d > 0:
        evidence["installs_30d"] = installs_30d

    return Candidate(
        repo=repo,
        name=name,
        stars=0,
        popularity=installs_30d,
        description=desc,
        homepage_url=homepage,
        download_url=download_url,
        source="brew",
        sources=["brew"],
        external_id=f"brew:{token}",
        platform=platform,
        link_kind=link_kind,
        fetcher="github_release" if repo else "download_page",
        evidences=[evidence],
    )


def _pending_brew_tokens(state: Any) -> set[str]:
    tokens: set[str] = set()
    if not state or not hasattr(state, "pending"):
        return tokens
    for item in getattr(state, "pending", []) or []:
        if not isinstance(item, dict):
            continue
        ext = str(item.get("external_id") or "")
        if ext.startswith("brew:"):
            tokens.add(ext.removeprefix("brew:").casefold())
        for ev in item.get("evidences") or []:
            if (
                isinstance(ev, dict)
                and ev.get("source") == "brew"
                and ev.get("external_id")
            ):
                tokens.add(str(ev["external_id"]).removeprefix("brew:").casefold())
    return tokens


def discover_popular(
    max_scan: int = DEFAULT_MAX_SCAN,
    *,
    state: Any = None,
    existing_id_set: set[str] | None = None,
    existing_brew_ids: set[str] | None = None,
    existing_homepage_set: set[str] | None = None,
    existing_repo_set: set[str] | None = None,
) -> list[Candidate]:
    """基于 Homebrew 30 天安装量排行榜发现未收录的热门 Cask。

    先从 analytics/cask-install/30d.json 获取排序榜单，过滤掉已收录和已拒绝的 token，
    再仅对排在前面的候选请求 cask/<token>.json 补全元数据。
    """
    global LAST_ERROR
    LAST_ERROR = None
    candidates: list[Candidate] = []

    try:
        analytics = get_json(_BREW_ANALYTICS_API, timeout=_TIMEOUT)
    except Exception as exc:
        LAST_ERROR = str(exc)
        if state and hasattr(state, "record_retry"):
            state.record_retry("brew:analytics:30d", str(exc))
        return candidates

    items = analytics.get("items") if isinstance(analytics, dict) else None
    if not isinstance(items, list):
        return candidates

    if existing_id_set is None:
        existing_id_set = existing_ids()
    if existing_brew_ids is None:
        existing_brew_ids = {
            ident for prov, ident in existing_source_ids() if prov == "brew"
        }
    if existing_homepage_set is None:
        existing_homepage_set = existing_homepages()
    if existing_repo_set is None:
        existing_repo_set = existing_repos()

    pending_tokens = _pending_brew_tokens(state)

    ranked: list[tuple[int, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        token = str(item.get("cask") or "").strip()
        # 跳过第三方 tap（含 /）、带版本后缀的别名（含 @）以及字体包（font-*）
        if not token or "/" in token or "@" in token or token.startswith("font-"):
            continue
        if token.casefold() in existing_brew_ids or token.casefold() in pending_tokens:
            continue
        slug = slugify(token)
        if slug and slug in existing_id_set:
            continue
        if state and hasattr(state, "is_rejected"):
            if (
                state.is_rejected(token)
                or state.is_rejected(f"brew:{token}")
                or (slug and state.is_rejected(slug))
            ):
                continue
        ranked.append((_parse_install_count(item.get("count")), token))

    ranked.sort(key=lambda pair: pair[0], reverse=True)
    batch = ranked[:max_scan]
    enriched = len(batch)
    enrichment_errors = 0
    last_enrich_err: str | None = None
    ordered_cands: list[tuple[int, Candidate]] = []

    def _enrich(
        pos: int, installs_30d: int, token: str
    ) -> tuple[int, int, str, dict[str, Any]]:
        cask = get_json(_BREW_CASK_API.format(token=token), timeout=_TIMEOUT)
        if not isinstance(cask, dict):
            raise ValueError(f"invalid cask metadata for {token}")
        return pos, installs_30d, token, cask

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_enrich, pos, installs_30d, token): (pos, token)
            for pos, (installs_30d, token) in enumerate(batch)
        }
        for fut in as_completed(futures):
            pos, token = futures[fut]
            try:
                _, installs_30d, _, cask = fut.result()
            except Exception as exc:
                enrichment_errors += 1
                last_enrich_err = str(exc)
                if state and hasattr(state, "record_retry"):
                    state.record_retry(f"brew:cask:{token}", str(exc))
                continue

            if cask.get("disabled") or cask.get("deprecated"):
                continue
            if state and hasattr(state, "record_success"):
                state.record_success(f"brew:cask:{token}")

            cand = _cask_to_candidate(cask, installs_30d=installs_30d)
            if cand is None:
                continue

            norm_hp = normalize_homepage(cand.homepage)
            if norm_hp and norm_hp in existing_homepage_set:
                continue
            if cand.repo and cand.repo.strip().lower() in existing_repo_set:
                continue
            cid = slugify(cand.name)
            if cid and cid in existing_id_set:
                continue

            ordered_cands.append((pos, cand))

    ordered_cands.sort(key=lambda pair: pair[0])
    candidates.extend(cand for _, cand in ordered_cands)

    if enriched > 0 and enrichment_errors == enriched and last_enrich_err:
        LAST_ERROR = last_enrich_err

    if state and hasattr(state, "update_cursor"):
        state.update_cursor(
            "brew_popular",
            {"scanned": enriched, "matched": len(candidates)},
        )

    return candidates


def load_brew_casks(*, force_refresh: bool = False) -> list[dict[str, Any]]:
    """进程内缓存完整 Homebrew Cask 列表，供跨源引用复用（只请求一次）。"""
    global _BREW_CATALOG_CACHE
    with _BREW_CATALOG_LOCK:
        if _BREW_CATALOG_CACHE is None or force_refresh:
            try:
                data = get_json(_BREW_API, timeout=_TIMEOUT)
                _BREW_CATALOG_CACHE = (
                    [c for c in data if isinstance(c, dict)]
                    if isinstance(data, list)
                    else []
                )
            except Exception:
                _BREW_CATALOG_CACHE = []
        return list(_BREW_CATALOG_CACHE)


def cross_reference_brew(
    candidates: list[Candidate],
    *,
    casks: list[dict[str, Any]] | None = None,
) -> list[Candidate]:
    """按 repo / 规范化 homepage 为其他源候选补全匹配的 Homebrew Cask 证据。"""
    if not candidates:
        return []
    catalog = casks if casks is not None else load_brew_casks()
    if not catalog:
        return []

    by_repo: dict[str, dict[str, Any]] = {}
    by_hp: dict[str, dict[str, Any]] = {}
    for cask in catalog:
        if not isinstance(cask, dict) or cask.get("disabled") or cask.get("deprecated"):
            continue
        hp = str(cask.get("homepage") or "").strip()
        url = str(cask.get("url") or "").strip()
        repo = extract_github_repo(hp) or extract_github_repo(url)
        if repo:
            by_repo.setdefault(repo.lower(), cask)
        norm_hp = normalize_homepage(hp)
        if norm_hp:
            by_hp.setdefault(norm_hp, cask)

    matched_cands: list[Candidate] = []
    seen_tokens: set[str] = set()
    for cand in candidates:
        if "brew" in cand.sources or cand.source == "brew":
            continue
        match: dict[str, Any] | None = None
        if cand.repo:
            match = by_repo.get(cand.repo.strip().lower())
        if match is None:
            norm_hp = normalize_homepage(cand.homepage)
            if norm_hp:
                match = by_hp.get(norm_hp)
        if match is None:
            continue
        token = str(match.get("token") or "").strip()
        if not token or token in seen_tokens:
            continue
        seen_tokens.add(token)
        brew_cand = _cask_to_candidate(match, installs_30d=cand.popularity)
        if brew_cand is not None:
            matched_cands.append(brew_cand)

    return matched_cands


def discover(
    max_scan: int = DEFAULT_MAX_SCAN,
    *,
    cursor: int = 0,
    state: Any = None,
    popular: bool = False,
) -> list[Candidate]:
    """通过 Homebrew Cask JSON API 发现软件。

    popular=True 时改用 30 天安装量排行榜（discover_popular）；
    默认 popular=False 保持游标增量扫描，兼容现有调用方与测试。
    """
    if popular:
        return discover_popular(max_scan=max_scan, state=state)

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

        cand = _cask_to_candidate(cask)
        if cand is not None:
            candidates.append(cand)

    if state and hasattr(state, "update_cursor"):
        state.update_cursor("brew", {"cursor": idx, "scanned": scanned})

    return candidates
