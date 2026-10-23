"""有界 HTTP 检查：验证目标域名、下载响应、平台线索及下载页身份。"""

from __future__ import annotations

import ipaddress
import re
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

from app_core.downloads import is_http_url, parse_time, url_expiry
from scripts.link_utils import is_direct_link
from scripts.net import base_headers, browser_headers, get

_GITHUB_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
_ARCH = {
    "arm64": r"(?:arm64|aarch64)",
    "x64": r"(?:x86_64|amd64|(?<![a-z0-9])x64)",
    "x86": r"(?:i[3-6]86|ia32|win32|(?<![a-z0-9])x86(?!_64))",
}
HTML_SAMPLE_BYTES = 512 * 1024

# 上游整站维护页的措辞。这类页面不属于"死链"，也不是反爬，而是上游
# 主动下线的临时状态；按真实失效处理会让整条发布流水线卡到上游恢复为止。
# 维护通告通常整站可见，因此直链被重定向到它、或落地页本身变成它时都按
# transient 处理；是否沿用旧验证结果由 validate_links 决定（要求旧结果仍有效）。
_MAINTENANCE_PHRASES = (
    "temporarily down for maintenance",
    "temporarily offline",
    "down for maintenance",
    "temporarily unavailable",
    "will be back shortly",
    "back up shortly",
    "undergoing maintenance",
    "scheduled maintenance",
    "维护中",
    "暂时无法访问",
    "临时维护",
    "系统维护",
)


def _html_evidence(text: str) -> str:
    # 脚本里的产品字串或错误提示不能充当页面身份、下载或维护证据。
    return re.sub(
        r"<(script|style)\b[^>]*>.*?(?:</\1\s*>|$)",
        " ",
        text,
        flags=re.I | re.S,
    )


_CHARSET_ALIASES = {"gb2312": "gb18030", "gbk": "gb18030"}


def _decode_html(sample: bytes, content_type: str) -> str:
    """按页面声明的字符集解码；国内站点多为 GBK/GB2312，按 UTF-8 硬解会丢正文。"""
    declared = ""
    match = re.search(r"charset=[\"']?([\w-]+)", content_type, re.I)
    if match:
        declared = match.group(1)
    else:
        match = re.search(
            rb"<meta[^>]+charset\s*=\s*[\"']?([\w-]+)", sample[:4096], re.I
        )
        if match:
            declared = match.group(1).decode("ascii", "ignore")
    charset = _CHARSET_ALIASES.get(declared.casefold(), declared or "utf-8")
    try:
        return sample.decode(charset, errors="replace")
    except LookupError:
        return sample.decode("utf-8", errors="replace")


def _looks_like_maintenance(text: str) -> bool:
    """判断 HTML 正文是否是上游整站维护/停机通告。"""
    normalized = _normal(_html_evidence(text))
    return any(phrase in normalized for phrase in _MAINTENANCE_PHRASES)


def _public_url(url: str) -> bool:
    if not is_http_url(url):
        return False
    host = urlsplit(url).hostname or ""
    if host == "localhost" or host.endswith((".localhost", ".local")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True


def _normal(value: str) -> str:
    return " ".join(re.findall(r"[\w]+", value.casefold()))


def _fetch_check(current: str, asset: dict, url: str):
    """GET 一个待检 URL（含一次 406 降级重试）。

    gitlab.gnome.org 的 generic package API 等端点对浏览器 UA 返回 406
    （bot 防护），但接受非浏览器 UA；先用浏览器 UA 请求，406 时换同步器
    UA 重试一次。重试仍失败则按原逻辑处理。
    """
    range_headers = (
        {"Range": "bytes=0-65535"}
        if is_direct_link(url, asset.get("link_kind"))
        else None
    )
    response = get(
        current,
        stream=True,
        allow_redirects=False,
        timeout=15,
        retries=1,
        headers=browser_headers(range_headers),
    )
    if response.status_code == 406:
        response.close()
        return get(
            current,
            stream=True,
            allow_redirects=False,
            timeout=15,
            retries=1,
            headers=base_headers(range_headers),
        )
    return response


def _platform_error(filename: str, platform: str) -> str | None:
    name = filename.lower()
    expected_arch = next(
        (arch for arch in _ARCH if platform.endswith("-" + arch)), None
    )
    found_arches = {arch for arch, pattern in _ARCH.items() if re.search(pattern, name)}
    if expected_arch and found_arches and expected_arch not in found_arches:
        return "download architecture conflicts with configured platform"
    if platform.startswith("win-") and name.endswith(
        (".dmg", ".pkg", ".deb", ".rpm", ".appimage", ".apk")
    ):
        return "non-Windows asset labeled as Windows"
    if platform.startswith("mac-") and name.endswith(
        (".exe", ".msi", ".deb", ".rpm", ".apk")
    ):
        return "non-macOS asset labeled as macOS"
    if platform.startswith("linux-") and name.endswith(
        (".exe", ".msi", ".dmg", ".pkg", ".apk")
    ):
        return "non-Linux asset labeled as Linux"
    return None


def verify_link(asset: dict, config: dict, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    url = asset["url"]
    result = {
        "status": "failed",
        "checked_at": now.isoformat(timespec="seconds"),
        "url": url,
    }
    expiry = url_expiry(url)
    declared_expiry = parse_time(asset.get("expires_at"))
    if declared_expiry:
        expiry = min(expiry, declared_expiry) if expiry else declared_expiry
    if expiry and expiry <= now + timedelta(minutes=5):
        return {**result, "reason": "signed URL expired or expires within five minutes"}
    if not _public_url(url):
        return {**result, "reason": "invalid or non-public HTTP URL"}
    settings = config.get("verification", {})
    allowed = {urlsplit(url).hostname, urlsplit(config.get("homepage", "")).hostname}
    allowed.update(settings.get("allowed_hosts", []))
    if (
        config.get("fetcher") == "github_release"
        or urlsplit(url).hostname == "github.com"
    ):
        allowed.update(_GITHUB_HOSTS)
    response = None
    current = url
    chain = []
    try:
        for _ in range(6):
            if not _public_url(current) or urlsplit(current).hostname not in allowed:
                return {
                    **result,
                    "status": "unverified",
                    "reason": "redirect host needs review",
                    "final_url": current,
                    "redirects": chain,
                }
            response = _fetch_check(current, asset, url)
            chain.append(current)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                response.close()
                if not location:
                    return {**result, "reason": "redirect without Location"}
                current = urljoin(current, location)
                continue
            break
        else:
            return {**result, "reason": "too many redirects"}
        result.update(
            final_url=current, redirects=chain, http_status=response.status_code
        )
        if response.status_code in {401, 403, 429}:
            return {
                **result,
                "status": "restricted",
                "reason": "upstream requires access or rate limited",
            }
        if response.status_code in {500, 502, 503, 504}:
            return {
                **result,
                "status": "transient",
                "reason": f"HTTP {response.status_code}",
            }
        if not 200 <= response.status_code < 300:
            return {**result, "reason": f"HTTP {response.status_code}"}
        # raw.read 有上界；服务端忽略 Range 也不下载完整安装包。
        sample = response.raw.read(
            65536 if is_direct_link(url, asset.get("link_kind")) else HTML_SAMPLE_BYTES,
            decode_content=True,
        )
        if not sample:
            return {**result, "reason": "empty response"}
        content_type = response.headers.get("Content-Type", "").lower()
        disposition = unquote(response.headers.get("Content-Disposition", ""))
        match = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", disposition, re.I)
        filename = (
            match.group(1)
            if match
            else unquote(PurePosixPath(urlsplit(current).path).name)
        )
        is_html = "html" in content_type or sample.lstrip().lower().startswith(
            (b"<!doctype html", b"<html")
        )
        if is_direct_link(url, asset.get("link_kind")):
            if is_html or "json" in content_type or "text/plain" in content_type:
                # 直链被重定向到上游维护页时按 transient 处理，与落地页口径一致；
                # 其余文档/错误页仍视为真实失效，不放行死链。
                if is_html and _looks_like_maintenance(
                    _decode_html(sample, content_type)
                ):
                    return {
                        **result,
                        "status": "transient",
                        "reason": "upstream maintenance page",
                    }
                return {
                    **result,
                    "reason": "expected installer, received a document/error page",
                }
            error = _platform_error(filename, asset.get("platform", ""))
            if error:
                return {**result, "reason": error}
            signatures = {
                ".exe": (b"MZ",),
                ".zip": (b"PK",),
                ".dmg": (),
                ".gz": (b"\x1f\x8b",),
                ".7z": (b"7z\xbc\xaf\x27\x1c",),
                ".msi": (b"\xd0\xcf\x11\xe0",),
                ".deb": (b"!<arch>\n",),
            }
            sigs = signatures.get(PurePosixPath(filename.lower()).suffix, ())
            if sigs and not sample.startswith(sigs):
                return {
                    **result,
                    "reason": "file header does not match installer format",
                }
            if not filename or not (
                "attachment" in disposition.lower()
                or sigs
                or content_type.startswith("application/")
            ):
                return {
                    **result,
                    "status": "unverified",
                    "reason": "insufficient download response evidence",
                }
            evidence = "trusted source, download response and platform filename checks"
        else:
            if not is_html:
                return {
                    **result,
                    "status": "unverified",
                    "reason": "expected an official download page",
                }
            raw_text = _decode_html(sample, content_type)
            text = _normal(_html_evidence(raw_text))
            # 上游整站维护/停机通告：既不是死链也不是反爬，单独标记以便门禁
            # 沿用仍未过期的上次验证结果，而不是阻塞整条发布流水线。
            if _looks_like_maintenance(raw_text):
                return {
                    **result,
                    "status": "transient",
                    "reason": "upstream maintenance page",
                }
            terms = settings.get("identity_terms") or [
                config.get("name", ""),
                config.get("id", ""),
            ]
            if not any(
                (
                    re.search(r"(?<!\w)" + re.escape(_normal(term)) + r"(?!\w)", text)
                    if _normal(term).isascii()
                    else _normal(term) in text
                )
                for term in terms
                if len(_normal(term)) >= 2
            ):
                return {
                    **result,
                    "status": "unverified",
                    "reason": "software identity not found on download page",
                }
            if not re.search(
                r"download|下载|获取|install|releases|app store|购买|buy|sign in|登录",
                text,
            ):
                return {
                    **result,
                    "status": "unverified",
                    "reason": "download/access entry not found on page",
                }
            evidence = "trusted source, product identity and download/access entry"
        valid_until = now + timedelta(days=7)
        if expiry:
            valid_until = min(valid_until, expiry - timedelta(minutes=5))
        return {
            **result,
            "status": "verified",
            "valid_until": valid_until.isoformat(timespec="seconds"),
            "filename": filename,
            "content_type": content_type,
            "evidence": evidence,
        }
    except Exception as exc:
        return {
            **result,
            "status": "unverified",
            "reason": f"network check failed: {type(exc).__name__}",
        }
    finally:
        if response is not None:
            response.close()
