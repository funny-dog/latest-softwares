"""Shared HTTP helpers for fetchers and validation scripts."""

from __future__ import annotations

from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import os
import threading
import time
from typing import Any
from urllib.parse import urlsplit

import requests


USER_AGENT = "latest-softwares-sync"
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 2
DEFAULT_BACKOFF = 1.0
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
# Retry-After 上限：避免上游传入异常大值（例如 86400）导致 CI 卡死
MAX_RETRY_AFTER = 60.0
MAX_CONNECTIONS_PER_HOST = max(
    1,
    int(os.environ.get("LATEST_SOFTWARES_MAX_CONNECTIONS_PER_HOST", "4")),
)
_HOST_LIMITERS: dict[str, threading.BoundedSemaphore] = {}
_HOST_LIMITERS_LOCK = threading.Lock()


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


def _host_key(url: str) -> str:
    parsed = urlsplit(url)
    return (parsed.netloc or url).lower()


def _get_host_limiter(url: str) -> threading.BoundedSemaphore:
    key = _host_key(url)
    with _HOST_LIMITERS_LOCK:
        limiter = _HOST_LIMITERS.get(key)
        if limiter is None:
            limiter = threading.BoundedSemaphore(MAX_CONNECTIONS_PER_HOST)
            _HOST_LIMITERS[key] = limiter
        return limiter


def _parse_retry_after(value: str | None) -> float | None:
    """解析 Retry-After 头，支持秒数与 HTTP-Date 两种格式。"""
    if not value:
        return None
    value = value.strip()
    try:
        return float(value)
    except ValueError:
        pass
    try:
        target = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if target is None:
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    delta = (target - datetime.now(tz=timezone.utc)).total_seconds()
    return max(delta, 0.0)


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
    host_limiter = _get_host_limiter(url)

    for attempt in range(retries + 1):
        retry_after: float | None = None
        try:
            with host_limiter:
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
            # 优先用服务端给的 Retry-After（GitHub 限流场景下最准）
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            response.close()

        if retry_after is not None:
            delay = min(retry_after, MAX_RETRY_AFTER)
        else:
            delay = float(backoff) * (2**attempt)
        time.sleep(delay)

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
