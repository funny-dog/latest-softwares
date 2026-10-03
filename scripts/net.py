"""Shared HTTP helpers for fetchers and validation scripts."""

from __future__ import annotations

import atexit
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import sys
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

# GitHub API 条件请求缓存：设置该环境变量（缓存文件路径）即开启。
# 命中 304 时复用上次的响应体，且不计入 GitHub primary rate limit。
HTTP_CACHE_ENV = "LATEST_SOFTWARES_HTTP_CACHE"
CONDITIONAL_CACHE_HOSTS = frozenset({"api.github.com"})
# 超过该天数未被使用的条目在保存时丢弃，防止缓存文件无限增长
HTTP_CACHE_MAX_IDLE_SECONDS = 14 * 86400


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


def set_max_connections_per_host(limit: int) -> None:
    """调整单 host 并发上限；须在发出请求前调用（已创建的 limiter 会被丢弃）。"""
    global MAX_CONNECTIONS_PER_HOST
    with _HOST_LIMITERS_LOCK:
        MAX_CONNECTIONS_PER_HOST = max(1, int(limit))
        _HOST_LIMITERS.clear()


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


class ConditionalCache:
    """按 URL 保存 ETag + 响应体的磁盘缓存（gzip JSON），线程安全。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0
        try:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                payload = json.load(fh)
            entries = payload.get("entries", {}) if isinstance(payload, dict) else {}
            if isinstance(entries, dict):
                self._entries = entries
        except FileNotFoundError:
            pass
        except Exception as exc:  # 缓存损坏不应影响抓取，丢弃重建即可
            print(f"HTTP cache load failed, ignoring: {exc}", file=sys.stderr)

    def lookup(self, url: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._entries.get(url)
            if isinstance(entry, dict) and entry.get("etag") and "body" in entry:
                return entry
            return None

    def hit(self, url: str) -> None:
        with self._lock:
            self.hits += 1
            entry = self._entries.get(url)
            if entry is not None:
                entry["used_at"] = time.time()

    def store(self, url: str, etag: str, body: str) -> None:
        with self._lock:
            self.misses += 1
            self._entries[url] = {"etag": etag, "body": body, "used_at": time.time()}

    def save(self) -> None:
        cutoff = time.time() - HTTP_CACHE_MAX_IDLE_SECONDS
        with self._lock:
            entries = {
                url: entry
                for url, entry in self._entries.items()
                if float(entry.get("used_at", 0)) >= cutoff
            }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as fh:
            json.dump({"version": 1, "entries": entries}, fh, ensure_ascii=False)
        os.replace(tmp, self.path)


_CONDITIONAL_CACHE: ConditionalCache | None = None
_CONDITIONAL_CACHE_LOCK = threading.Lock()


def _save_conditional_cache() -> None:
    cache = _CONDITIONAL_CACHE
    if cache is None:
        return
    try:
        cache.save()
    except Exception as exc:
        print(f"HTTP cache save failed: {exc}", file=sys.stderr)
        return
    if cache.hits or cache.misses:
        print(
            f"HTTP conditional cache: {cache.hits} x 304 reused, "
            f"{cache.misses} x 200 stored",
            file=sys.stderr,
        )


def _conditional_cache_for(url: str) -> ConditionalCache | None:
    """返回 URL 适用的条件请求缓存；未开启或 host 不在白名单时返回 None。"""
    global _CONDITIONAL_CACHE
    path = os.environ.get(HTTP_CACHE_ENV)
    if not path or urlsplit(url).hostname not in CONDITIONAL_CACHE_HOSTS:
        return None
    with _CONDITIONAL_CACHE_LOCK:
        if _CONDITIONAL_CACHE is None or _CONDITIONAL_CACHE.path != Path(path):
            if _CONDITIONAL_CACHE is None:
                atexit.register(_save_conditional_cache)
            else:
                _save_conditional_cache()
            _CONDITIONAL_CACHE = ConditionalCache(Path(path))
        return _CONDITIONAL_CACHE


def get_json(url: str, **kwargs: Any) -> Any:
    cache = _conditional_cache_for(url)
    entry = cache.lookup(url) if cache is not None else None
    if entry is not None:
        kwargs["headers"] = {
            **(kwargs.get("headers") or {}),
            "If-None-Match": entry["etag"],
        }

    response = get(url, **kwargs)
    if cache is not None and entry is not None and response.status_code == 304:
        response.close()
        cache.hit(url)
        return json.loads(entry["body"])

    response.raise_for_status()
    data = response.json()
    etag = response.headers.get("ETag") if cache is not None else None
    if cache is not None and etag:
        cache.store(url, etag, response.text)
    return data
