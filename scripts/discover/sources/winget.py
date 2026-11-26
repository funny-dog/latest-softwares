"""WinGet 软件发现：支持 GitHub tree 游标扫描与微软 source2.msix 索引查询。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import io
import os
import re
import sqlite3
import tempfile
import threading
from typing import Any
import zipfile

import yaml

from ...fetchers.base import FetchError
from ...fetchers.package_manifest import select_winget_installer
from ...net import get, get_json, github_headers
from ..models import DEFAULT_MAX_SCAN, Candidate
from ..state import DiscoveryState
from ..url_utils import extract_github_repo, is_valid_http_url, normalize_homepage

_API = "https://api.github.com/repos/microsoft/winget-pkgs"
WINGET_RAW_BASE = "https://raw.githubusercontent.com/microsoft/winget-pkgs/master"
WINGET_INDEX_URL = "https://cdn.winget.microsoft.com/cache/source2.msix"
_PARTITIONS = "abcdefghijklmnopqrstuvwxyz0123456789"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_VARIANT_SUFFIXES = (
    ".arm64",
    ".x86",
    ".beta",
    ".dev",
    ".canary",
    ".insiders",
    ".nightly",
)

LAST_ERROR: str | None = None

_WINGET_INDEX_LOCK = threading.Lock()
_WINGET_INDEX_CACHE: WinGetIndex | None = None


def _norm_token(value: str) -> str:
    return _NON_ALNUM.sub("", value.strip().lower())


@dataclass(frozen=True)
class WinGetIndexEntry:
    id: str
    name: str
    moniker: str
    version: str
    norm_names: tuple[str, ...] = ()
    norm_publishers: tuple[str, ...] = ()


class WinGetIndex:
    """内存中的 WinGet source2.msix 包索引，支持按名称、moniker 与 publisher 快速检索。"""

    def __init__(self, entries: list[WinGetIndexEntry]) -> None:
        self.entries = entries
        self.by_id: dict[str, WinGetIndexEntry] = {}
        self.by_norm_name: dict[str, list[WinGetIndexEntry]] = {}
        self.by_moniker: dict[str, list[WinGetIndexEntry]] = {}
        self.by_id_tail: dict[str, list[WinGetIndexEntry]] = {}
        self.by_publisher: dict[str, list[WinGetIndexEntry]] = {}

        for entry in entries:
            self.by_id[entry.id] = entry
            if entry.moniker:
                self.by_moniker.setdefault(_norm_token(entry.moniker), []).append(entry)
            for nn in entry.norm_names:
                if nn:
                    self.by_norm_name.setdefault(nn, []).append(entry)
            name_norm = _norm_token(entry.name)
            if name_norm and name_norm not in entry.norm_names:
                self.by_norm_name.setdefault(name_norm, []).append(entry)
            tail = entry.id.split(".", 1)[-1]
            tail_norm = _norm_token(tail)
            if tail_norm:
                self.by_id_tail.setdefault(tail_norm, []).append(entry)
            for np in entry.norm_publishers:
                if np:
                    self.by_publisher.setdefault(np, []).append(entry)
            pub_prefix = _norm_token(entry.id.split(".", 1)[0])
            if pub_prefix and pub_prefix not in entry.norm_publishers:
                self.by_publisher.setdefault(pub_prefix, []).append(entry)

    def get(self, package_id: str) -> WinGetIndexEntry | None:
        return self.by_id.get(package_id)

    def lookup_by_publisher(
        self, publisher: str, *, limit: int = 20
    ) -> list[WinGetIndexEntry]:
        key = _norm_token(publisher)
        if not key:
            return []
        matches = list(self.by_publisher.get(key, []))
        matches.sort(
            key=lambda e: (e.id.lower().endswith(_VARIANT_SUFFIXES), len(e.id), e.id)
        )
        return matches[:limit]

    def lookup(
        self, query: str = "", *, publisher: str = "", limit: int = 10
    ) -> list[WinGetIndexEntry]:
        nq = _norm_token(query)
        np = _norm_token(publisher)
        if not nq and np:
            return self.lookup_by_publisher(publisher, limit=limit)
        if not nq:
            return []

        raw: list[WinGetIndexEntry] = []
        raw.extend(self.by_moniker.get(nq, []))
        raw.extend(self.by_norm_name.get(nq, []))
        raw.extend(self.by_id_tail.get(nq, []))

        deduped: dict[str, WinGetIndexEntry] = {}
        for entry in raw:
            deduped.setdefault(entry.id, entry)

        candidates = list(deduped.values())
        if np:
            pub_filtered = [
                e
                for e in candidates
                if np in e.norm_publishers or _norm_token(e.id.split(".", 1)[0]) == np
            ]
            if pub_filtered:
                candidates = pub_filtered

        def _rank(entry: WinGetIndexEntry) -> tuple[int, int, int, int, str]:
            is_variant = int(entry.id.lower().endswith(_VARIANT_SUFFIXES))
            moniker_match = (
                int(_norm_token(entry.moniker) != nq) if entry.moniker else 1
            )
            exact_name = int(_norm_token(entry.name) != nq)
            return (
                is_variant,
                moniker_match,
                exact_name,
                entry.id.count("."),
                entry.id,
            )

        candidates.sort(key=_rank)
        return candidates[:limit]


def parse_winget_index_msix(content: bytes) -> WinGetIndex:
    """从微软官方 WinGet source2.msix（ZIP + SQLite）解析完整包索引。"""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        db_bytes = zf.read("Public/index.db")
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    try:
        with os.fdopen(fd, "wb") as tf:
            tf.write(db_bytes)
        conn = sqlite3.connect(tmp_path)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            pkg_rows = conn.execute(
                "SELECT rowid, id, name, moniker, latest_version FROM packages "
                "WHERE latest_version IS NOT NULL"
            ).fetchall()

            norm_names_map: dict[int, list[str]] = {}
            if "norm_names2" in tables:
                for nn, pkg_rowid in conn.execute(
                    "SELECT norm_name, package FROM norm_names2"
                ).fetchall():
                    if nn:
                        norm_names_map.setdefault(int(pkg_rowid), []).append(str(nn))

            norm_pubs_map: dict[int, list[str]] = {}
            if "norm_publishers2" in tables:
                for np, pkg_rowid in conn.execute(
                    "SELECT norm_publisher, package FROM norm_publishers2"
                ).fetchall():
                    if np:
                        norm_pubs_map.setdefault(int(pkg_rowid), []).append(str(np))
        finally:
            conn.close()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    entries: list[WinGetIndexEntry] = []
    for rowid, pkg_id, name, moniker, ver in pkg_rows:
        if not pkg_id or not ver:
            continue
        rid = int(rowid)
        entries.append(
            WinGetIndexEntry(
                id=str(pkg_id),
                name=str(name or pkg_id),
                moniker=str(moniker or ""),
                version=str(ver),
                norm_names=tuple(norm_names_map.get(rid, ())),
                norm_publishers=tuple(norm_pubs_map.get(rid, ())),
            )
        )
    return WinGetIndex(entries)


def load_winget_index(*, force_refresh: bool = False) -> WinGetIndex | None:
    """进程内缓存 WinGet source2.msix 索引；不可用时返回 None。"""
    global _WINGET_INDEX_CACHE
    with _WINGET_INDEX_LOCK:
        if _WINGET_INDEX_CACHE is None or force_refresh:
            try:
                resp = get(WINGET_INDEX_URL, timeout=30, retries=2)
                try:
                    resp.raise_for_status()
                    _WINGET_INDEX_CACHE = parse_winget_index_msix(resp.content)
                finally:
                    resp.close()
            except Exception:
                _WINGET_INDEX_CACHE = None
        return _WINGET_INDEX_CACHE


def parse_manifest_yaml(content: str) -> dict[str, Any] | None:
    try:
        value = yaml.safe_load(content)
        return value if isinstance(value, dict) else None
    except yaml.YAMLError:
        return None


def extract_installer_url(manifest: dict[str, Any]) -> tuple[str | None, str]:
    for arch, platform in (
        ("x64", "win-x64"),
        ("arm64", "win-arm64"),
        ("x86", "win-x86"),
        ("neutral", "win"),
    ):
        if not any(
            item.get("Architecture", manifest.get("Architecture")) == arch
            for item in manifest.get("Installers", [])
        ):
            continue
        try:
            installer = select_winget_installer(manifest, arch)
        except FetchError:
            return None, platform
        url = installer.get("InstallerUrl", manifest.get("InstallerUrl"))
        return (str(url), platform) if is_valid_http_url(url) else (None, platform)
    return None, "win"


def _version_key(value: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (1, int(v)) if v.isdigit() else (0, v.casefold())
        for v in re.split(r"(\d+)", value)
    )


def _fetch_raw_yaml(url: str) -> dict[str, Any] | None:
    resp = get(url, timeout=30)
    try:
        if hasattr(resp, "status_code") and resp.status_code == 404:
            return None
        if hasattr(resp, "raise_for_status"):
            resp.raise_for_status()
        return parse_manifest_yaml(resp.text)
    finally:
        resp.close()


def fetch_winget_manifest_candidate(
    package_id: str,
    version: str,
    *,
    popularity: int = 0,
) -> Candidate | None:
    """按确定性 raw.githubusercontent.com 路径读取 WinGet 清单并组装 Candidate（零 GitHub API 消耗）。"""
    parts = package_id.split(".")
    if len(parts) < 2 or not parts[0]:
        return None
    base = (
        f"{WINGET_RAW_BASE}/manifests/{parts[0][0].lower()}/"
        + "/".join(parts)
        + f"/{version}/{package_id}"
    )

    manifest = _fetch_raw_yaml(base + ".installer.yaml")
    if manifest is None:
        manifest = _fetch_raw_yaml(base + ".yaml")
    if not manifest or manifest.get("PackageIdentifier") != package_id:
        return None

    locale = _fetch_raw_yaml(base + ".locale.en-US.yaml")
    if locale is not None and locale.get("PackageIdentifier") == package_id:
        installers = manifest.get("Installers")
        manifest.update(locale)
        if installers and "Installers" not in manifest:
            manifest["Installers"] = installers

    url, platform = extract_installer_url(manifest)
    if not url:
        return None

    homepage = str(manifest.get("PackageUrl") or "").strip()
    repo = extract_github_repo(homepage) or extract_github_repo(url) or ""
    return Candidate(
        repo=repo,
        name=str(manifest.get("PackageName") or package_id),
        popularity=popularity,
        description=str(
            manifest.get("ShortDescription") or manifest.get("Description") or ""
        ),
        source="winget",
        external_id=package_id,
        homepage_url=homepage,
        download_url=url,
        platform=platform,
        link_kind="direct",
        fetcher="package_manifest",
    )


def search_winget_by_publisher(
    publisher: str,
    *,
    max_scan: int = 10,
    index: WinGetIndex | None = None,
) -> list[Candidate]:
    """按 publisher 搜索 source2.msix 索引并拉取对应 WinGet 清单。"""
    idx = index or load_winget_index()
    if idx is None:
        return []
    entries = idx.lookup_by_publisher(publisher, limit=max_scan)
    results: list[Candidate] = []
    for entry in entries:
        try:
            cand = fetch_winget_manifest_candidate(entry.id, entry.version)
        except Exception:
            continue
        if cand is not None:
            results.append(cand)
    return results


def _candidate_search_terms(cand: Candidate) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        clean = raw.strip()
        norm = _norm_token(clean)
        if clean and norm and norm not in seen:
            seen.add(norm)
            terms.append(clean)

    _add(cand.name)
    if cand.source == "brew" and cand.external_id:
        _add(cand.external_id.removeprefix("brew:"))
    if cand.repo:
        _add(cand.repo.split("/")[-1])
    return terms


def _identities_match(a: Candidate, b: Candidate) -> bool:
    if a.repo and b.repo and a.repo.strip().casefold() == b.repo.strip().casefold():
        return True
    hp_a = normalize_homepage(a.homepage)
    hp_b = normalize_homepage(b.homepage)
    return bool(hp_a and hp_b and hp_a == hp_b)


def corroborate_with_winget_index(
    candidates: list[Candidate],
    *,
    index: WinGetIndex | None = None,
    max_lookups: int = 40,
) -> list[Candidate]:
    """用 source2.msix 索引为 Brew / Flathub / GitHub 候选自动匹配已验证身份的 WinGet ID。"""
    if not candidates or max_lookups <= 0:
        return []
    idx = index or load_winget_index()
    if idx is None:
        return []

    prioritized = sorted(
        candidates,
        key=lambda c: max(c.popularity, c.stars),
        reverse=True,
    )

    jobs: list[tuple[int, Candidate, list[WinGetIndexEntry]]] = []
    planned_lookups = 0
    for pos, cand in enumerate(prioritized):
        if planned_lookups >= max_lookups:
            break
        if "winget" in cand.sources or cand.source == "winget":
            continue
        if not cand.repo and not normalize_homepage(cand.homepage):
            continue

        candidate_entries: list[WinGetIndexEntry] = []
        seen_entry_ids: set[str] = set()
        for term in _candidate_search_terms(cand):
            for entry in idx.lookup(term, limit=3):
                if entry.id not in seen_entry_ids:
                    seen_entry_ids.add(entry.id)
                    candidate_entries.append(entry)
        trimmed = candidate_entries[: min(3, max_lookups - planned_lookups)]
        if trimmed:
            planned_lookups += len(trimmed)
            jobs.append((pos, cand, trimmed))

    def _match_one(
        pos: int, cand: Candidate, entries: list[WinGetIndexEntry]
    ) -> tuple[int, Candidate | None]:
        for entry in entries:
            try:
                wg_cand = fetch_winget_manifest_candidate(
                    entry.id, entry.version, popularity=cand.popularity
                )
            except Exception:
                continue
            if wg_cand is not None and _identities_match(cand, wg_cand):
                return pos, wg_cand
        return pos, None

    matched_ordered: list[tuple[int, Candidate]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(_match_one, pos, cand, entries) for pos, cand, entries in jobs
        ]
        for fut in as_completed(futures):
            pos, wg_cand = fut.result()
            if wg_cand is not None:
                matched_ordered.append((pos, wg_cand))

    matched_ordered.sort(key=lambda pair: pair[0])
    matched: list[Candidate] = []
    seen_winget_ids: set[str] = set()
    for _, wg_cand in matched_ordered:
        if wg_cand.external_id not in seen_winget_ids:
            seen_winget_ids.add(wg_cand.external_id)
            matched.append(wg_cand)
    return matched


def discover_from_index(
    max_scan: int = DEFAULT_MAX_SCAN,
    *,
    cursor: int = 0,
    state: DiscoveryState | None = None,
    index: WinGetIndex | None = None,
) -> list[Candidate]:
    """基于 source2.msix 索引与 raw.githubusercontent.com 游标扫描 WinGet，避免 GitHub API 树遍历。"""
    global LAST_ERROR
    LAST_ERROR = None
    idx = index or load_winget_index()
    if idx is None:
        LAST_ERROR = "WinGet source2.msix index unavailable"
        if state:
            state.record_retry("winget:index:source2.msix", LAST_ERROR)
        return []

    total = len(idx.entries)
    if total == 0:
        return []

    saved = state.get_cursor("winget_index", {}) if state else {}
    cur = int(saved.get("cursor", cursor)) if isinstance(saved, dict) else cursor
    pos = cur % total
    scanned = 0
    candidates: list[Candidate] = []

    while scanned < max_scan and scanned < total:
        entry = idx.entries[pos]
        pos = (pos + 1) % total
        scanned += 1
        try:
            cand = fetch_winget_manifest_candidate(entry.id, entry.version)
        except Exception as exc:
            LAST_ERROR = str(exc)
            if state:
                state.record_retry(f"winget:{entry.id}", str(exc))
            continue
        if cand is not None:
            candidates.append(cand)
            if state:
                state.record_success(f"winget:{entry.id}")

    if state:
        state.update_cursor("winget_index", {"cursor": pos, "scanned": scanned})
    return candidates


def discover(
    max_scan: int = DEFAULT_MAX_SCAN,
    *,
    partition: str | None = None,
    cursor: int = 0,
    state: DiscoveryState | None = None,
    use_index: bool = False,
) -> list[Candidate]:
    if use_index:
        return discover_from_index(max_scan=max_scan, cursor=cursor, state=state)

    global LAST_ERROR
    LAST_ERROR = None
    saved = state.get_cursor("winget", {}) if state else {}
    part_idx = int(saved.get("partition_index", 0)) % len(_PARTITIONS)
    part = partition or _PARTITIONS[part_idx]
    publisher_idx = int(saved.get("publisher_index", 0))
    offset = int(saved.get("package_offset", cursor))
    candidates = []
    scanned = 0
    try:
        publishers = get_json(
            f"{_API}/contents/manifests/{part}", headers=github_headers(), timeout=30
        )
        if not isinstance(publishers, list):
            raise ValueError("invalid WinGet publisher directory")
        publishers = [p for p in publishers if p.get("type") == "dir"]
        while publisher_idx < len(publishers) and scanned < max_scan:
            publisher = publishers[publisher_idx]
            tree = get_json(
                f"{_API}/git/trees/{publisher['sha']}?recursive=1",
                headers=github_headers(),
                timeout=30,
            )
            if (
                not isinstance(tree, dict)
                or tree.get("truncated")
                or not isinstance(tree.get("tree"), list)
            ):
                raise ValueError("WinGet tree incomplete; narrower partition required")
            files = {f["path"] for f in tree["tree"] if f.get("type") == "blob"}
            latest: dict[str, tuple[str, str]] = {}
            for path in sorted(files):
                if not path.endswith(".installer.yaml"):
                    continue
                name = path.rsplit("/", 1)[-1].removesuffix(".installer.yaml")
                version = path.split("/")[-2] if "/" in path else ""
                if name not in latest or _version_key(version) > _version_key(
                    latest[name][0]
                ):
                    latest[name] = (version, path)
            choices = sorted(latest.items())
            # 空 publisher 也消耗扫描预算，避免一轮无限遍历无效目录。
            if not choices:
                scanned += 1
            while offset < len(choices) and scanned < max_scan:
                package_id, (_, path) = choices[offset]
                scanned += 1
                base = f"https://raw.githubusercontent.com/microsoft/winget-pkgs/master/{publisher['path']}/"
                response = get(base + path, timeout=30)
                try:
                    manifest = parse_manifest_yaml(response.text) or {}
                finally:
                    response.close()
                if manifest.get("PackageIdentifier") != package_id:
                    raise ValueError("WinGet manifest identity mismatch")
                locale_path = (
                    path.removesuffix(".installer.yaml") + ".locale.en-US.yaml"
                )
                if locale_path in files:
                    response = get(base + locale_path, timeout=30)
                    try:
                        locale = parse_manifest_yaml(response.text) or {}
                    finally:
                        response.close()
                    if locale.get("PackageIdentifier") != package_id:
                        raise ValueError("WinGet locale identity mismatch")
                    manifest.update(locale)
                url, platform = extract_installer_url(manifest)
                homepage = str(manifest.get("PackageUrl") or "")
                candidates.append(
                    Candidate(
                        repo=extract_github_repo(homepage)
                        or extract_github_repo(url)
                        or "",
                        name=str(manifest.get("PackageName") or package_id),
                        description=str(
                            manifest.get("ShortDescription")
                            or manifest.get("Description")
                            or ""
                        ),
                        source="winget",
                        external_id=package_id,
                        homepage_url=homepage,
                        download_url=url or "",
                        platform=platform,
                        link_kind="direct",
                        fetcher="package_manifest",
                    )
                )
                offset += 1
                if state:
                    state.record_success(f"winget:{package_id}")
            if offset >= len(choices):
                publisher_idx += 1
                offset = 0
        if publisher_idx >= len(publishers):
            part_idx = (part_idx + 1) % len(_PARTITIONS)
            publisher_idx = offset = 0
    except Exception as exc:
        LAST_ERROR = str(exc)
        if state:
            state.record_retry(f"winget:partition:{part}", str(exc))
    if state:
        state.update_cursor(
            "winget",
            {
                "partition_index": part_idx,
                "publisher_index": publisher_idx,
                "package_offset": offset,
            },
        )
    return candidates
