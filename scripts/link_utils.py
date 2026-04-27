"""Shared link classification helpers."""

from __future__ import annotations

from urllib.parse import urlsplit


DIRECT_FILE_EXTENSIONS = (
    ".exe",
    ".dmg",
    ".iso",
    ".zip",
    ".tar.gz",
    ".msi",
    ".pkg",
    ".deb",
    ".rpm",
    ".appimage",
    ".7z",
)


def is_direct_link(url: str) -> bool:
    """Return whether a URL points at a direct downloadable file."""
    if not url:
        return False
    path = urlsplit(url).path.lower()
    return path.endswith(DIRECT_FILE_EXTENSIONS)
