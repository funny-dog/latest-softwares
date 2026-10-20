"""discover 包公共数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 翻译失败时的 desc_cn 占位符（人工 review 时替换）
PLACEHOLDER_DESC_CN = "TODO: 待人工补充中文描述"

# CLI 默认参数
DEFAULT_MIN_STARS = 5000
DEFAULT_MAX_OUTPUT = 10
DEFAULT_MAX_SCAN = 100  # 最多扫描多少个候选 repo / manifest
DEFAULT_MAX_CORROBORATE = 30  # 最多对多少候选做 code search 佐证
DEFAULT_SOURCES = ["github"]
ALL_SUPPORTED_SOURCES = ["github", "winget", "brew", "scoop"]
DEFAULT_STATE_FILE = "data/discovery-state.json"
DEFAULT_REVIEW_FILE = "data/discovery-candidates.json"


@dataclass
class Candidate:
    repo: str = ""  # owner/repo（闭源或独立官网条目可为空）
    name: str = ""  # 显示名（默认取 repo 名或 manifest 名）
    stars: int = 0
    description: str = ""  # repo / 软件描述，可能为空串
    topics: list[str] = field(default_factory=list)
    asset_names: list[str] = field(default_factory=list)  # latest release 资产文件名
    released_at: str | None = None
    # 多源扩展字段
    homepage_url: str = ""  # 官方主页
    download_url: str = ""  # 直接/官网下载链接
    source: str = "github"  # 发现源：github, winget, brew, scoop
    external_id: str = (
        ""  # 外部稳定唯一标识符 (例如 Microsoft.VisualStudioCode, google-chrome)
    )
    sources: list[str] = field(default_factory=list)  # 发现或佐证该候选的所有源
    evidences: list[dict[str, Any]] = field(default_factory=list)  # 来源证据列表
    platform: str = "win-x64"  # 目标平台 (如 win-x64, mac-universal)
    link_kind: str | None = None  # direct 或 landing_page
    fetcher: str = "github_release"  # 期望的 fetcher 类型

    def __post_init__(self) -> None:
        if self.source and not self.sources:
            self.sources = [self.source]
        if not self.evidences and (
            self.source or self.external_id or self.download_url
        ):
            evidence: dict[str, Any] = {"source": self.source}
            if self.external_id:
                evidence["external_id"] = self.external_id
            if self.homepage_url:
                evidence["homepage"] = self.homepage_url
            if self.download_url:
                evidence["url"] = self.download_url
            self.evidences.append(evidence)

    @property
    def homepage(self) -> str:
        if self.homepage_url:
            return self.homepage_url
        if self.repo:
            return f"https://github.com/{self.repo}"
        return ""

    def manifest_ids(self) -> dict[str, str]:
        result = {}
        for evidence in self.evidences:
            source, ident = evidence.get("source"), evidence.get("external_id")
            if source not in {"winget", "brew", "scoop"} or not ident:
                continue
            ident = str(ident).removeprefix(f"{source}:")
            if source == "scoop" and "/" not in ident:
                bucket = (
                    evidence.get("bucket", "ScoopInstaller/Main").split("/")[-1].lower()
                )
                ident = f"{bucket}/{ident}"
            if source in result and result[source] != ident:
                raise ValueError(
                    f"conflicting {source} identities: {result[source]} vs {ident}"
                )
            result[source] = ident
        return result

    def to_dict(self) -> dict[str, Any]:
        """转为字典供审查文件或序列化使用。"""
        return {
            "name": self.name,
            "repo": self.repo,
            "homepage": self.homepage,
            "download_url": self.download_url,
            "platform": self.platform,
            "fetcher": self.fetcher,
            "sources": self.sources,
            "external_id": self.external_id,
            "stars": self.stars,
            "description": self.description,
            "evidences": self.evidences,
        }
