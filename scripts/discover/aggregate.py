"""编排：多源候选去重、证据映射、冲突判定、可靠链接过滤、佐证与截断。

规则：
- 不把名字相同当同一软件，通过 repo / 官方 homepage / 稳定外部 id 建立证据映射。
- 候选来源之间有冲突（同名歧义、元数据矛盾）进入 review-file，遇到歧义不要随便取第一个。
- 官方链接 metadata 可生成 download_page 条目，GitHub 条目仍用唯一可靠资产匹配。
- 闭源/非 Windows 软件可作为候选。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from .asset_infer import infer_windows_pattern
from .dedup import existing_homepages, existing_ids, existing_repos, existing_source_ids
from .generate import slugify
from .models import Candidate
from .sources.corroborate import is_corroborated
from .url_utils import is_valid_http_url, normalize_homepage


@dataclass
class SoftwareCluster:
    """代表同一个软件的多源聚合簇。"""

    name: str
    repo: str = ""
    homepage_url: str = ""
    download_url: str = ""
    stars: int = 0
    description: str = ""
    topics: list[str] = field(default_factory=list)
    asset_names: list[str] = field(default_factory=list)
    released_at: str | None = None
    sources: set[str] = field(default_factory=set)
    external_ids: set[str] = field(default_factory=set)
    evidences: list[dict[str, Any]] = field(default_factory=list)
    platform: str = "win-x64"
    fetcher: str = "github_release"
    has_conflict: bool = False
    conflict_detail: str = ""
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def homepage(self) -> str:
        if self.homepage_url:
            return self.homepage_url
        if self.repo:
            return f"https://github.com/{self.repo}"
        return ""

    def to_candidate(self) -> Candidate:
        return Candidate(
            repo=self.repo,
            name=self.name,
            stars=self.stars,
            description=self.description,
            topics=self.topics,
            asset_names=self.asset_names,
            released_at=self.released_at,
            homepage_url=self.homepage_url,
            download_url=self.download_url,
            source=sorted(self.sources)[0] if self.sources else "unknown",
            sources=sorted(self.sources),
            external_id=sorted(self.external_ids)[0] if self.external_ids else "",
            evidences=self.evidences,
            platform=self.platform,
            fetcher=self.fetcher,
        )


def _cluster_candidates(candidates: list[Candidate]) -> list[SoftwareCluster]:
    """将候选列表按 repo / homepage / external_id 聚合为 Cluster。"""
    clusters: list[SoftwareCluster] = []
    repo_to_cluster: dict[str, SoftwareCluster] = {}
    hp_to_cluster: dict[str, SoftwareCluster] = {}
    ext_to_cluster: dict[str, SoftwareCluster] = {}

    for c in candidates:
        r_key = c.repo.strip().lower() if c.repo else ""
        hp_key = normalize_homepage(c.homepage)
        ext_key = f"{c.source}:{c.external_id.strip().lower()}" if c.external_id else ""

        matched: SoftwareCluster | None = None
        if r_key and r_key in repo_to_cluster:
            matched = repo_to_cluster[r_key]
        elif hp_key and hp_key in hp_to_cluster:
            matched = hp_to_cluster[hp_key]
        elif ext_key and ext_key in ext_to_cluster:
            matched = ext_to_cluster[ext_key]

        if matched is None:
            # 新建簇
            cl = SoftwareCluster(
                name=c.name or (c.repo.split("/")[-1] if c.repo else ""),
                repo=c.repo,
                homepage_url=c.homepage_url,
                download_url=c.download_url,
                stars=c.stars,
                description=c.description,
                topics=list(c.topics),
                asset_names=list(c.asset_names),
                released_at=c.released_at,
                sources=set(c.sources),
                external_ids={c.external_id} if c.external_id else set(),
                evidences=list(c.evidences),
                platform=c.platform,
                fetcher=c.fetcher,
                candidates=[c],
            )
            clusters.append(cl)
            if r_key:
                repo_to_cluster[r_key] = cl
            if hp_key:
                hp_to_cluster[hp_key] = cl
            if ext_key:
                ext_to_cluster[ext_key] = cl
        else:
            for other in (
                repo_to_cluster.get(r_key),
                hp_to_cluster.get(hp_key),
                ext_to_cluster.get(ext_key),
            ):
                if other is not None and other is not matched:
                    other.has_conflict = matched.has_conflict = True
                    other.conflict_detail = matched.conflict_detail = (
                        "identity evidence bridges conflicting software clusters"
                    )
            if matched.repo and c.repo and matched.repo.casefold() != c.repo.casefold():
                matched.has_conflict = True
                matched.conflict_detail = (
                    f"repository conflict: {matched.repo} vs {c.repo}"
                )
            # 合并证据与信息
            matched.candidates.append(c)
            matched.sources.update(c.sources)
            if c.external_id:
                matched.external_ids.add(c.external_id)
            for evidence in c.evidences:
                if evidence not in matched.evidences:
                    matched.evidences.append(evidence)
            if not matched.repo and c.repo:
                matched.repo = c.repo
                if r_key:
                    repo_to_cluster[r_key] = matched
            if not matched.homepage_url and c.homepage_url:
                matched.homepage_url = c.homepage_url
                if hp_key:
                    hp_to_cluster[hp_key] = matched
            if not matched.download_url and c.download_url:
                matched.download_url = c.download_url
            if c.stars > matched.stars:
                matched.stars = c.stars
            if not matched.description and c.description:
                matched.description = c.description
            if c.asset_names:
                matched.asset_names = list(c.asset_names)
            if not matched.topics and c.topics:
                matched.topics = list(c.topics)

            # 跨源元数据冲突检查（如两个不同来源给出的独立顶级域名 homepage 完全不同）
            if (
                matched.homepage_url
                and c.homepage_url
                and normalize_homepage(matched.homepage_url)
                != normalize_homepage(c.homepage_url)
            ):
                matched.has_conflict = True
                matched.conflict_detail = (
                    f"主页冲突: {matched.homepage_url} vs {c.homepage_url}"
                )

    return clusters


def select_candidates(
    candidates: list[Candidate],
    *,
    max_output: int,
    max_corroborate: int,
    review_manager: Any = None,
    state: Any = None,
) -> list[tuple[Candidate, str]]:
    """返回 [(candidate, windows_pattern), ...]，已过滤+排序+截断。

    向后兼容老测试；支持 review_manager 记录未选中的冲突与无可靠链接项。
    """
    existing_rep = existing_repos()
    existing_id_set = existing_ids()
    existing_hp_set = existing_homepages()
    source_id_set = existing_source_ids()

    # 1. 跨源聚合为软件簇
    clusters = _cluster_candidates(candidates)

    # 2. 检查簇内元数据冲突
    non_conflicting_clusters: list[SoftwareCluster] = []
    for cl in clusters:
        cand_id = slugify(cl.name)
        try:
            cl.to_candidate().manifest_ids()
        except ValueError as exc:
            cl.has_conflict = True
            cl.conflict_detail = str(exc)
        if cl.has_conflict:
            if review_manager and hasattr(review_manager, "add"):
                review_manager.add(
                    id=cand_id,
                    name=cl.name,
                    reason="conflict",
                    detail=f"多源元数据冲突: {cl.conflict_detail}",
                    sources=list(cl.sources),
                    candidates=cl.candidates,
                )
            continue
        non_conflicting_clusters.append(cl)

    # 3. 同名歧义冲突判定（不把名字相同当同一软件，遇到歧义不要随便取第一个）
    id_to_clusters: dict[str, list[SoftwareCluster]] = defaultdict(list)
    for cl in non_conflicting_clusters:
        cid = slugify(cl.name)
        id_to_clusters[cid].append(cl)

    unambiguous_clusters: list[SoftwareCluster] = []
    for cid, cl_list in id_to_clusters.items():
        if len(cl_list) > 1:
            # 存在同名歧义冲突：不要随便取第一个，全部进入 review-file
            details = "; ".join(
                f"{c.name} (homepage={c.homepage}, repo={c.repo})" for c in cl_list
            )
            if review_manager and hasattr(review_manager, "add"):
                for cl in cl_list:
                    review_manager.add(
                        id=cid,
                        name=cl.name,
                        reason="conflict",
                        detail=f"同名歧义冲突（多个不同软件对应同一 ID '{cid}'）：{details}",
                        sources=list(cl.sources),
                        candidates=cl.candidates,
                    )
            continue
        unambiguous_clusters.append(cl_list[0])

    # 4. 状态与现有库去重
    survivors: list[tuple[SoftwareCluster, str]] = []
    for cl in unambiguous_clusters:
        cid = slugify(cl.name)

        # 检查是否在跨轮已拒绝名单中
        if state and hasattr(state, "is_rejected"):
            identities = [cid, cl.repo] + [
                f"{p}:{i}" for p, i in cl.to_candidate().manifest_ids().items()
            ]
            if any(state.is_rejected(ident) for ident in identities):
                if review_manager and hasattr(review_manager, "add"):
                    review_manager.add(
                        id=cid,
                        name=cl.name,
                        reason="rejected",
                        detail="已被标记为跨轮拒绝候选",
                        sources=list(cl.sources),
                        candidates=cl.candidates,
                    )
                continue

        if any(
            (provider, ident.casefold()) in source_id_set
            for provider, ident in cl.to_candidate().manifest_ids().items()
        ):
            continue

        # 检查是否已收录在 packages/ 中
        if cl.repo and cl.repo.strip().lower() in existing_rep:
            continue
        norm_hp = normalize_homepage(cl.homepage)
        if norm_hp and norm_hp in existing_hp_set:
            continue
        if not cid or cid in existing_id_set:
            if review_manager and hasattr(review_manager, "add"):
                review_manager.add(
                    id=cid,
                    name=cl.name,
                    reason="conflict",
                    detail=f"ID '{cid}' 与现有 packages 清单条目冲突",
                    sources=list(cl.sources),
                    candidates=cl.candidates,
                )
            continue

        # 5. 可靠链接与资产匹配判定
        pattern: str = ""
        fetcher = "github_release"

        if cl.asset_names:
            # 拥有 release 资产的 GitHub 软件：要求唯一可靠资产匹配
            inferred = infer_windows_pattern(cl.asset_names)
            if inferred is not None:
                pattern = inferred
                fetcher = "github_release"
                cl.platform = "win-x64"
            else:
                # 资产推断失败，检查是否有官方下载链接降级为 download_page
                if is_valid_http_url(cl.download_url):
                    fetcher = "download_page"
                    pattern = ""
                else:
                    if review_manager and hasattr(review_manager, "add"):
                        review_manager.add(
                            id=cid,
                            name=cl.name,
                            reason="no_reliable_link",
                            detail=f"无法从资产列表推断 Windows pattern: {cl.asset_names}",
                            sources=list(cl.sources),
                            candidates=cl.candidates,
                        )
                    continue
        else:
            # 无 GitHub release 资产（闭源、非 Windows 或官方直链软件）
            if is_valid_http_url(cl.download_url):
                fetcher = "download_page"
                pattern = ""
            else:
                if review_manager and hasattr(review_manager, "add"):
                    review_manager.add(
                        id=cid,
                        name=cl.name,
                        reason="no_reliable_link",
                        detail="缺少有效的 http(s) 官方直链或资产",
                        sources=list(cl.sources),
                        candidates=cl.candidates,
                    )
                continue

        cl.fetcher = fetcher
        survivors.append((cl, pattern))

    # 按 star 降序，并优先多源交叉佐证的
    survivors.sort(
        key=lambda cp: (cp[0].stars, len(cp[0].sources)),
        reverse=True,
    )
    if state is not None:
        state.pending = [asdict(cl.to_candidate()) for cl, _ in survivors]

    # 6. 多源佐证（对于 GitHub 纯单源候选）与数量截断
    selected: list[tuple[Candidate, str]] = []
    checked = 0
    for cl, pattern in survivors:
        if len(selected) >= max_output:
            break

        cand = cl.to_candidate()
        # 若已有 >= 2 个源发现（如 github + winget/brew/scoop），天然属于多源交叉验证
        if (
            cl.sources & {"winget", "brew", "scoop"}
            or len(cl.sources) >= 2
            or not cand.repo
        ):
            selected.append((cand, pattern))
            continue

        # 单源 GitHub 候选：执行有上限的 code search 佐证
        if checked >= max_corroborate:
            break
        checked += 1
        if is_corroborated(cand.repo):
            selected.append((cand, pattern))
        else:
            if review_manager and hasattr(review_manager, "add"):
                review_manager.add(
                    id=slugify(cand.name),
                    name=cand.name,
                    reason="skipped",
                    detail="未通过 winget/Scoop 代码搜索多源佐证",
                    sources=cand.sources,
                    candidates=[cand],
                )

    return selected
