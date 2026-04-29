"""Fetcher 注册表 —— 加新类型只需在这里加一行。"""

from __future__ import annotations

from typing import Callable

from .base import FetchResult, FetchError, AssetInfo
from . import (
    github_release,
    windows11_fido,
    vscode,
    chrome,
    steam,
    firefox,
    nodejs,
    download_page,
    wegame,
    baidunetdisk,
    geek,
    everything,
    ubuntu,
    fedora,
)
from . import nvidia_app, qq, wechat, yy


FETCHERS: dict[str, Callable[[dict], FetchResult]] = {
    "github_release": github_release.fetch,
    "windows11_fido": windows11_fido.fetch,
    "vscode_official": vscode.fetch,
    "chrome_official": chrome.fetch,
    "steam_official": steam.fetch,
    "firefox_official": firefox.fetch,
    "nodejs_official": nodejs.fetch,
    "download_page": download_page.fetch,
    "wegame_official": wegame.fetch,
    "baidunetdisk": baidunetdisk.fetch,
    "geek": geek.fetch,
    "everything": everything.fetch,
    "nvidia_app": nvidia_app.fetch,
    "qq_official": qq.fetch,
    "wechat_official": wechat.fetch,
    "yy_official": yy.fetch,
    "ubuntu_releases": ubuntu.fetch,
    "fedora_releases": fedora.fetch,
}


__all__ = ["FETCHERS", "FetchResult", "FetchError", "AssetInfo"]
