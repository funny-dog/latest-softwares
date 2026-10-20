"""下载入口的共享有效性规则；运行时只读验证结果，不请求上游。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlsplit


def parse_time(value: str | None) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
        return dt.replace(tzinfo=timezone.utc) if dt and dt.tzinfo is None else dt
    except (ValueError, TypeError, AttributeError):
        return None


def is_http_url(value: object) -> bool:
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return False
    try:
        url = urlsplit(value)
        return (
            url.scheme in {"https", "http"}
            and bool(url.hostname)
            and not (url.username or url.password)
        )
    except ValueError:
        return False


def url_expiry(url: str) -> datetime | None:
    """识别常见签名 URL；未知格式由每次检查的有效期兜底。"""
    query = {k.lower(): v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    try:
        if "x-amz-date" in query and "x-amz-expires" in query:
            from datetime import timedelta

            return datetime.strptime(query["x-amz-date"], "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            ) + timedelta(seconds=int(query["x-amz-expires"]))
        if "se" in query:
            return parse_time(query["se"])
        for key in ("expires", "p1"):
            if key in query and query[key].isdigit():
                return datetime.fromtimestamp(int(query[key]), timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return None


def asset_available(asset: dict[str, Any], now: datetime | None = None) -> bool:
    if not is_http_url(asset.get("url")):
        return False
    now = now or datetime.now(timezone.utc)
    verification = asset.get("verification")
    # 旧快照兼容；新发布由 coverage 门禁要求每个入口附验证结果。
    if verification is not None:
        if verification.get("url", asset["url"]) != asset["url"]:
            return False
        if verification.get("status") != "verified":
            return False
        valid_until = parse_time(verification.get("valid_until"))
        if valid_until is None or valid_until <= now:
            return False
    expires = url_expiry(asset["url"])
    declared_expiry = parse_time(asset.get("expires_at"))
    if declared_expiry and declared_expiry <= now:
        return False
    return expires is None or expires > now
