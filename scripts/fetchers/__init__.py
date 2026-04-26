"""Fetcher 注册表 —— 加新类型只需在这里加一行。"""
from __future__ import annotations

from typing import Callable

from .base import FetchResult, FetchError, AssetInfo
from . import github_release, windows11_fido, vscode, chrome


FETCHERS: dict[str, Callable[[dict], FetchResult]] = {
    "github_release":  github_release.fetch,
    "windows11_fido":  windows11_fido.fetch,
    "vscode_official": vscode.fetch,
    "chrome_official": chrome.fetch,
}


__all__ = ["FETCHERS", "FetchResult", "FetchError", "AssetInfo"]
