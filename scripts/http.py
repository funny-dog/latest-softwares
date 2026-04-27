"""Shared HTTP helpers for fetchers and validation scripts."""

from __future__ import annotations

import os
import time
from typing import Any

import requests


USER_AGENT = "latest-softwares-sync"
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF = 1.0
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def base_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return default request headers, preserving caller overrides."""
    headers = {"User-Agent": USER_AGENT}
    if extra:
        headers.update(extra)
    return headers


def github_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return GitHub API headers, including GITHUB_TOKEN when available."""
    headers = base_headers(
        {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if extra:
        headers.update(extra)
    return headers


def browser_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return browser-like headers for static download pages."""
    headers = base_headers(
        {
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    if extra:
        headers.update(extra)
    return headers


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int | float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: int | float = DEFAULT_BACKOFF,
    **kwargs: Any,
) -> requests.Response:
    """Run an HTTP request with default headers and light transient retries."""
    merged_headers = base_headers(headers)
    last_exc: requests.RequestException | None = None

    for attempt in range(retries + 1):
        try:
            response = requests.request(
                method,
                url,
                headers=merged_headers,
                timeout=timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= retries:
                raise
        else:
            if response.status_code not in RETRY_STATUS_CODES or attempt >= retries:
                return response
            response.close()

        time.sleep(float(backoff) * (2**attempt))

    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"request retry loop exhausted for {method} {url}")


def get(url: str, **kwargs: Any) -> requests.Response:
    return request("GET", url, **kwargs)


def head(url: str, **kwargs: Any) -> requests.Response:
    return request("HEAD", url, **kwargs)


def get_json(url: str, **kwargs: Any) -> Any:
    response = get(url, **kwargs)
    response.raise_for_status()
    return response.json()
