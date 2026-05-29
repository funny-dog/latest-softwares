"""编排：把 GitHub 候选过滤（资产可推断 + 去重 + 多源佐证）、按 star 排序、截断。

调用顺序刻意为：先做无 API 成本的资产推断与去重，再对幸存者做
有限次（max_corroborate）的 code search 佐证，控制 GitHub 限额消耗。
"""

from __future__ import annotations

from .asset_infer import infer_windows_pattern
from .dedup import existing_repos, is_new
from .models import Candidate
from .sources.corroborate import is_corroborated


def select_candidates(
    candidates: list[Candidate],
    *,
    max_output: int,
    max_corroborate: int,
) -> list[tuple[Candidate, str]]:
    """返回 [(candidate, windows_pattern), ...]，已过滤+排序+截断。"""
    existing = existing_repos()

    # ① 资产可推断 + ② 去重（无 API 成本），同时记下 pattern
    prefiltered: list[tuple[Candidate, str]] = []
    for c in candidates:
        if not is_new(c, existing):
            continue
        pattern = infer_windows_pattern(c.asset_names)
        if pattern is None:
            continue
        prefiltered.append((c, pattern))

    # 按 star 降序，保证先佐证最热门的
    prefiltered.sort(key=lambda cp: cp[0].stars, reverse=True)

    # ③ 多源佐证（有限次 code search）
    selected: list[tuple[Candidate, str]] = []
    checked = 0
    for c, pattern in prefiltered:
        if len(selected) >= max_output:
            break
        if checked >= max_corroborate:
            break
        checked += 1
        if is_corroborated(c.repo):
            selected.append((c, pattern))
    return selected
