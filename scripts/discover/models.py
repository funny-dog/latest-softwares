"""discover 包公共数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field

# 翻译失败时的 desc_cn 占位符（人工 review 时替换）
PLACEHOLDER_DESC_CN = "TODO: 待人工补充中文描述"

# CLI 默认参数
DEFAULT_MIN_STARS = 5000
DEFAULT_MAX_OUTPUT = 10
DEFAULT_MAX_SCAN = 100  # 最多扫描多少个高星 repo
DEFAULT_MAX_CORROBORATE = 30  # 最多对多少候选做 code search 佐证


@dataclass
class Candidate:
    repo: str  # owner/repo
    name: str  # 显示名（默认取 repo 名）
    stars: int
    description: str  # repo 描述，可能为空串
    topics: list[str] = field(default_factory=list)
    asset_names: list[str] = field(default_factory=list)  # latest release 资产文件名
    released_at: str | None = None

    @property
    def homepage(self) -> str:
        return f"https://github.com/{self.repo}"
