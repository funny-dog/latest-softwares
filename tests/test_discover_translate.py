from __future__ import annotations

from scripts.discover import translate
from scripts.discover.models import PLACEHOLDER_DESC_CN


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


def test_translate_success(monkeypatch):
    def fake_get(url, **kwargs):
        assert "mymemory" in url
        return _FakeResp({"responseData": {"translatedText": "USB 启动盘制作工具"}})

    monkeypatch.setattr(translate, "get", fake_get)
    assert (
        translate.translate_to_zh("USB bootable drive creator") == "USB 启动盘制作工具"
    )


def test_translate_empty_input_returns_placeholder():
    assert translate.translate_to_zh("") == PLACEHOLDER_DESC_CN


def test_translate_http_failure_returns_placeholder(monkeypatch):
    def fake_get(url, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(translate, "get", fake_get)
    assert translate.translate_to_zh("anything") == PLACEHOLDER_DESC_CN


def test_translate_bad_payload_returns_placeholder(monkeypatch):
    def fake_get(url, **kwargs):
        return _FakeResp({"responseData": {"translatedText": ""}})

    monkeypatch.setattr(translate, "get", fake_get)
    assert translate.translate_to_zh("anything") == PLACEHOLDER_DESC_CN
