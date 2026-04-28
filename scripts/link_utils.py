"""Shared link classification helpers."""

from __future__ import annotations

from urllib.parse import urlsplit

LINK_KIND_DIRECT = "direct"
LINK_KIND_LANDING_PAGE = "landing_page"
LINK_KINDS = {LINK_KIND_DIRECT, LINK_KIND_LANDING_PAGE}

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


def normalize_link_kind(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def is_direct_link(url: str, link_kind: str | None = None) -> bool:
    """Return whether a URL points at a direct downloadable file."""
    kind = normalize_link_kind(link_kind)
    if kind == LINK_KIND_DIRECT:
        return True
    if kind == LINK_KIND_LANDING_PAGE:
        return False
    if not url:
        return False
    path = urlsplit(url).path.lower()
    return path.endswith(DIRECT_FILE_EXTENSIONS)
