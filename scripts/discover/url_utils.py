"""discover URL 验证与规范化工具。"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app_core.downloads import is_http_url

_TEMPLATE_VAR = re.compile(r"(\$\{[^}]+\}|#\{[^}]+\}|%[a-zA-Z0-9_]+%)")
_GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+?)(?:/.*)?$"
)
_GENERIC_HOSTS = {
    "github.com",
    "gitlab.com",
    "sourceforge.net",
    "bitbucket.org",
    "gitee.com",
    "codeberg.org",
}


def is_valid_http_url(url: str | None) -> bool:
    """检查 URL 是否为合法的 http(s) 链接，拒绝脚本、危险命令和未解析模板。"""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url:
        return False
    if _TEMPLATE_VAR.search(url):
        return False
    return is_http_url(url)


def extract_github_repo(url: str | None) -> str | None:
    """尝试从 URL 中提取 GitHub owner/repo。"""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    m = _GITHUB_REPO_RE.match(url)
    if not m:
        return None
    repo = m.group(1).removesuffix(".git")
    if "/" in repo:
        parts = repo.split("/")
        if len(parts) == 2 and parts[0] and parts[1]:
            return f"{parts[0]}/{parts[1]}"
    return None


def normalize_homepage(url: str | None) -> str:
    """规范化官方主页用于同一软件去重对比。

    去除 http/https 协议差异、www. 前缀和尾部斜杠；
    排除通用代码托管平台根域名（避免将所有托管在 GitHub 的软件视作同一软件）。
    """
    if not url or not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    try:
        parsed = urlparse(url)
    except Exception:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/")
    if netloc in _GENERIC_HOSTS and (not path or path.count("/") < 2):
        return ""
    return f"{netloc}{path}".lower()
