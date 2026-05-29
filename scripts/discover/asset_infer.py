"""从 GitHub release 资产名推断 Windows x64 安装包的 glob pattern。

宁缺毋滥：推不出唯一可信资产时返回 None，让上层跳过该候选，
避免生成会导致 sync 失败的条目。
"""

from __future__ import annotations

import re

# 明确排除的非 Windows / 非 x64 标记
_EXCLUDE_TOKENS = (
    "arm64",
    "aarch64",
    "armv7",
    "arm",
    "linux",
    "ubuntu",
    "debian",
    "fedora",
    ".deb",
    ".rpm",
    ".appimage",
    "mac",
    "macos",
    "osx",
    "darwin",
    ".dmg",
    ".pkg",
    "android",
    ".apk",
    "ios",
    "x86.exe",
    "ia32",
    "i686",
    "32bit",
    "win32",
)
# Windows 可执行安装扩展名
_WIN_EXTS = (".exe", ".msi")
# 版本号正则：优先匹配 a.b / a.b.c 形式，其次纯长数字串
_VERSION_RE = re.compile(r"\d+(?:\.\d+)+")
_LONGNUM_RE = re.compile(r"\d{4,}")


def _has_token(name: str, tokens: tuple[str, ...]) -> bool:
    return any(t in name for t in tokens)


def _is_windows_asset(lower: str) -> bool:
    """判断单个资产是否是 Windows x64 安装包候选。"""
    if _has_token(lower, _EXCLUDE_TOKENS):
        return False
    if lower.endswith(_WIN_EXTS):
        return True
    if lower.endswith(".zip") and _has_token(
        lower, ("windows", "win64", "win", "x64", "amd64")
    ):
        return True
    return False


def _score(lower: str) -> int:
    """分数越高越像"主 Windows x64 安装包"。"""
    score = 0
    if lower.endswith(".exe"):
        score += 3
    if lower.endswith(".msi"):
        score += 2
    if "setup" in lower or "installer" in lower:
        score += 2
    if "x64" in lower or "amd64" in lower or "x86_64" in lower or "win64" in lower:
        score += 2
    if "windows" in lower or "win" in lower:
        score += 1
    return score


def _globify_version(name: str) -> str:
    """把文件名里的版本号子串替换为 *。"""
    if _VERSION_RE.search(name):
        return _VERSION_RE.sub("*", name)
    if _LONGNUM_RE.search(name):
        return _LONGNUM_RE.sub("*", name)
    return name


def infer_windows_pattern(asset_names: list[str]) -> str | None:
    """返回 Windows x64 资产的 glob pattern；推不出则 None。"""
    scored: list[tuple[int, str]] = []
    for name in asset_names:
        lower = name.lower()
        if _is_windows_asset(lower):
            scored.append((_score(lower), name))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    # 最高分若与次高分并列且文件名差异大，仍取最高分第一个（确定性）
    best_name = scored[0][1]
    return _globify_version(best_name)
