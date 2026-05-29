from __future__ import annotations

from scripts.discover.sources import corroborate


def test_winget_corroborated_when_code_search_has_hits(monkeypatch):
    def fake_get_json(url, **kwargs):
        assert "search/code" in url
        assert "winget-pkgs" in url
        return {"total_count": 3}

    monkeypatch.setattr(corroborate, "get_json", fake_get_json)
    assert corroborate.corroborated_by_winget("pbatard/rufus") is True


def test_scoop_not_corroborated_when_zero_hits(monkeypatch):
    def fake_get_json(url, **kwargs):
        return {"total_count": 0}

    monkeypatch.setattr(corroborate, "get_json", fake_get_json)
    assert corroborate.corroborated_by_scoop("obscure/repo") is False


def test_corroboration_failure_is_false_not_exception(monkeypatch):
    def fake_get_json(url, **kwargs):
        raise RuntimeError("rate limited")

    monkeypatch.setattr(corroborate, "get_json", fake_get_json)
    assert corroborate.corroborated_by_winget("a/b") is False


def test_is_corroborated_true_if_either_source(monkeypatch):
    calls = []

    def fake_get_json(url, **kwargs):
        calls.append(url)
        # winget 命中即短路，不应再查 scoop
        return {"total_count": 1}

    monkeypatch.setattr(corroborate, "get_json", fake_get_json)
    assert corroborate.is_corroborated("pbatard/rufus") is True
    assert len(calls) == 1  # 短路
