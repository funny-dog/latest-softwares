"""发现源：Flathub Popular / Trending API v2。

通过 flathub.org/api/v2/collection/popular（与 trending）获取热门开源/桌面应用，
并按需通过 appstream/<app_id> 补全官方主页与仓库元数据，供与 WinGet / Brew 交叉比对。
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ...net import get_json
from ..dedup import existing_homepages, existing_ids, existing_repos
from ..generate import slugify
from ..models import DEFAULT_MAX_SCAN, Candidate
from ..url_utils import extract_github_repo, is_valid_http_url, normalize_homepage

_FLATHUB_POPULAR_API = "https://flathub.org/api/v2/collection/popular"
_FLATHUB_TRENDING_API = "https://flathub.org/api/v2/collection/trending"
_FLATHUB_APPSTREAM_API = "https://flathub.org/api/v2/appstream/{app_id}"
_TIMEOUT = 30

LAST_ERROR: str | None = None


def _extract_non_flathub_repo(url: str | None) -> str:
    repo = extract_github_repo(url)
    if not repo:
        return ""
    # Flathub 打包仓库本身不是上游软件仓库
    if repo.split("/", 1)[0].casefold() == "flathub":
        return ""
    return repo


def _pending_flathub_ids(state: Any) -> set[str]:
    ids: set[str] = set()
    if not state or not hasattr(state, "pending"):
        return ids
    for item in getattr(state, "pending", []) or []:
        if not isinstance(item, dict):
            continue
        ext = str(item.get("external_id") or "")
        if ext.startswith("flathub:"):
            ids.add(ext.removeprefix("flathub:").casefold())
        for ev in item.get("evidences") or []:
            if (
                isinstance(ev, dict)
                and ev.get("source") == "flathub"
                and ev.get("external_id")
            ):
                ids.add(str(ev["external_id"]).removeprefix("flathub:").casefold())
    return ids


def _fetch_collection_hits(url: str) -> list[dict[str, Any]]:
    data = get_json(url, timeout=_TIMEOUT)
    if isinstance(data, dict):
        hits = data.get("hits", [])
        return (
            [h for h in hits if isinstance(h, dict)] if isinstance(hits, list) else []
        )
    if isinstance(data, list):
        return [h for h in data if isinstance(h, dict)]
    return []


def discover(
    max_scan: int = DEFAULT_MAX_SCAN,
    *,
    state: Any = None,
    include_trending: bool = True,
    existing_id_set: set[str] | None = None,
    existing_homepage_set: set[str] | None = None,
    existing_repo_set: set[str] | None = None,
) -> list[Candidate]:
    """从 Flathub Popular（及可选 Trending）集合发现热门软件候选。"""
    global LAST_ERROR
    LAST_ERROR = None
    candidates: list[Candidate] = []

    try:
        popular_hits = _fetch_collection_hits(_FLATHUB_POPULAR_API)
    except Exception as exc:
        LAST_ERROR = str(exc)
        if state and hasattr(state, "record_retry"):
            state.record_retry("flathub:collection:popular", str(exc))
        return candidates

    merged_hits: list[dict[str, Any]] = []
    seen_app_ids: set[str] = set()
    for hit in popular_hits:
        app_id = str(hit.get("app_id") or hit.get("id") or "").strip()
        if not app_id or app_id in seen_app_ids:
            continue
        seen_app_ids.add(app_id)
        merged_hits.append(hit)

    if include_trending:
        try:
            trending_hits = _fetch_collection_hits(_FLATHUB_TRENDING_API)
        except Exception as exc:
            # Trending 失败不阻塞 Popular 主结果
            if state and hasattr(state, "record_retry"):
                state.record_retry("flathub:collection:trending", str(exc))
            trending_hits = []
        for hit in trending_hits:
            app_id = str(hit.get("app_id") or hit.get("id") or "").strip()
            if not app_id or app_id in seen_app_ids:
                continue
            seen_app_ids.add(app_id)
            merged_hits.append(hit)

    if existing_id_set is None:
        existing_id_set = existing_ids()
    if existing_homepage_set is None:
        existing_homepage_set = existing_homepages()
    if existing_repo_set is None:
        existing_repo_set = existing_repos()

    pending_ids = _pending_flathub_ids(state)

    filtered_hits: list[tuple[int, dict[str, Any], str]] = []
    for hit in merged_hits:
        app_id = str(hit.get("app_id") or hit.get("id") or "").strip()
        name = str(hit.get("name") or "").strip()
        if not app_id or not name:
            continue
        if app_id.casefold() in pending_ids:
            continue
        cid = slugify(name)
        if cid and cid in existing_id_set:
            continue
        ver_site = str(hit.get("verification_website") or "").strip()
        if ver_site:
            ver_hp = (
                ver_site
                if ver_site.startswith(("http://", "https://"))
                else f"https://{ver_site}"
            )
            norm_ver = normalize_homepage(ver_hp)
            if norm_ver and norm_ver in existing_homepage_set:
                continue
        if state and hasattr(state, "is_rejected"):
            if (
                state.is_rejected(app_id)
                or state.is_rejected(f"flathub:{app_id}")
                or (cid and state.is_rejected(cid))
            ):
                continue
        installs = int(hit.get("installs_last_month") or 0)
        filtered_hits.append((installs, hit, app_id))

    filtered_hits.sort(key=lambda item: item[0], reverse=True)
    batch = filtered_hits[:max_scan]
    enriched = len(batch)
    enrichment_errors = 0
    last_enrich_err: str | None = None
    ordered_cands: list[tuple[int, Candidate]] = []

    def _enrich_hit(
        pos: int, installs: int, hit: dict[str, Any], app_id: str
    ) -> tuple[int, int, dict[str, Any], str, dict[str, Any]]:
        raw_app = get_json(
            _FLATHUB_APPSTREAM_API.format(app_id=app_id), timeout=_TIMEOUT
        )
        if not isinstance(raw_app, dict):
            raise ValueError(f"invalid flathub appstream for {app_id}")
        return pos, installs, hit, app_id, raw_app

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_enrich_hit, pos, installs, hit, app_id): (pos, app_id)
            for pos, (installs, hit, app_id) in enumerate(batch)
        }
        for fut in as_completed(futures):
            pos, app_id = futures[fut]
            try:
                _, installs, hit, _, appstream = fut.result()
                if state and hasattr(state, "record_success"):
                    state.record_success(f"flathub:appstream:{app_id}")
            except Exception as exc:
                enrichment_errors += 1
                last_enrich_err = str(exc)
                if state and hasattr(state, "record_retry"):
                    state.record_retry(f"flathub:appstream:{app_id}", str(exc))
                continue

            if appstream.get("is_eol"):
                continue

            raw_urls = appstream.get("urls")
            urls: dict[str, Any] = raw_urls if isinstance(raw_urls, dict) else {}
            homepage = str(urls.get("homepage") or "").strip()
            if not is_valid_http_url(homepage):
                ver_site = str(hit.get("verification_website") or "").strip()
                candidate_hp = (
                    ver_site
                    if ver_site.startswith(("http://", "https://"))
                    else f"https://{ver_site}"
                    if ver_site
                    else ""
                )
                homepage = candidate_hp if is_valid_http_url(candidate_hp) else ""

            repo = (
                _extract_non_flathub_repo(urls.get("vcs_browser"))
                or _extract_non_flathub_repo(homepage)
                or _extract_non_flathub_repo(urls.get("bugtracker"))
            )
            if not homepage and repo:
                homepage = f"https://github.com/{repo}"

            norm_hp = normalize_homepage(homepage)
            if norm_hp and norm_hp in existing_homepage_set:
                continue
            if repo and repo.lower() in existing_repo_set:
                continue

            name = str(appstream.get("name") or hit.get("name") or app_id).strip()
            summary = str(appstream.get("summary") or hit.get("summary") or "").strip()
            raw_cats = appstream.get("categories") or hit.get("main_categories") or []
            if isinstance(raw_cats, str):
                topics = [raw_cats.lower()]
            elif isinstance(raw_cats, list):
                topics = [str(c).strip().lower() for c in raw_cats if str(c).strip()]
            else:
                topics = []

            evidence: dict[str, Any] = {
                "source": "flathub",
                "external_id": app_id,
                "homepage": homepage,
                "installs_last_month": installs,
            }
            trending_val = hit.get("trending")
            if isinstance(trending_val, (int, float)):
                evidence["trending"] = float(trending_val)

            ordered_cands.append(
                (
                    pos,
                    Candidate(
                        repo=repo,
                        name=name,
                        stars=0,
                        popularity=installs,
                        description=summary,
                        topics=topics,
                        homepage_url=homepage,
                        download_url="",
                        source="flathub",
                        sources=["flathub"],
                        external_id=f"flathub:{app_id}",
                        platform="linux-x64",
                        link_kind=None,
                        fetcher="github_release" if repo else "download_page",
                        evidences=[evidence],
                    ),
                )
            )

    ordered_cands.sort(key=lambda pair: pair[0])
    candidates.extend(cand for _, cand in ordered_cands)

    if enriched > 0 and enrichment_errors == enriched and last_enrich_err:
        LAST_ERROR = last_enrich_err

    if state and hasattr(state, "update_cursor"):
        state.update_cursor(
            "flathub",
            {"scanned": enriched, "matched": len(candidates)},
        )

    return candidates
