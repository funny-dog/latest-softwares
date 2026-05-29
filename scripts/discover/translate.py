"""desc_cn 翻译后端：MyMemory（免 key）。

容错优先：任何失败都降级为占位符，绝不抛异常中断整个发现流程。
后端做成可替换：未来可换 DeepL，只需替换 translate_to_zh 内部实现。
"""

from __future__ import annotations

from urllib.parse import urlencode

from ..net import get
from .models import PLACEHOLDER_DESC_CN

_MYMEMORY_API = "https://api.mymemory.translated.net/get"
_TIMEOUT = 15


def translate_to_zh(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return PLACEHOLDER_DESC_CN
    params = urlencode({"q": text, "langpair": "en|zh-CN"})
    url = f"{_MYMEMORY_API}?{params}"
    try:
        resp = get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        translated = (data.get("responseData") or {}).get("translatedText") or ""
        translated = translated.strip()
        return translated if translated else PLACEHOLDER_DESC_CN
    except Exception:
        return PLACEHOLDER_DESC_CN
