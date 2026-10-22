from types import SimpleNamespace

import pytest

from scripts.fetchers import FETCHERS, aliyundrive
from scripts.fetchers.base import FetchError
from scripts.validate_config import validate_config

HTML = """
<script>var Global = {
latest_version: 'V2.1.7',
app_windows_download_link: 'https://cdn.aliyundrive.net/downloads/apps/desktop/aDrive-6.9.3.exe',
app_mac_download_link: 'https://cdn.aliyundrive.net/downloads/apps/desktop/aDrive-6.9.3.dmg',
app_mac_arm64_download_link: 'https://cdn.aliyundrive.net/downloads/apps/desktop/aDrive-6.9.3-arm64.dmg',
};</script>
"""
ARGS = {"platforms": [{"platform": p} for p in aliyundrive.CLIENTS]}


def mock_page(monkeypatch, html):
    closed = []
    response = SimpleNamespace(
        raw=SimpleNamespace(read=lambda size, **kw: html.encode()[:size]),
        raise_for_status=lambda: None,
        close=lambda: closed.append(True),
    )
    monkeypatch.setattr(aliyundrive, "get", lambda *a, **kw: response)
    return closed


def test_official_client_links_supply_real_version_and_architectures(monkeypatch):
    closed = mock_page(monkeypatch, HTML)
    result = FETCHERS["aliyundrive_official"](ARGS)
    assert result.version == "6.9.3"
    assert result.version_kind == "release_version"
    assert [a.platform for a in result.assets] == list(aliyundrive.CLIENTS)
    assert result.assets[-1].url.endswith("-arm64.dmg")
    assert all(a.link_kind == "direct" for a in result.assets)
    assert closed == [True]


@pytest.mark.parametrize(
    "html",
    [
        HTML.replace("app_mac_download_link", "missing_key"),
        HTML.replace("cdn.aliyundrive.net", "untrusted.example"),
        HTML.replace("aDrive-6.9.3.exe", "aDrive-6.9.4.exe"),
        HTML + HTML,
        "<div id='root'></div>",
    ],
)
def test_incomplete_or_conflicting_official_configuration_fails_closed(
    monkeypatch, html
):
    closed = mock_page(monkeypatch, html)
    with pytest.raises(FetchError):
        aliyundrive.fetch(ARGS)
    assert closed == [True]


def test_unsupported_platform_is_rejected_by_config_validation():
    errors = validate_config(
        {
            "packages": [
                {
                    "id": "aliyundrive",
                    "name": "阿里云盘",
                    "category": "Utilities",
                    "fetcher": "aliyundrive_official",
                    "args": {"platforms": [{"platform": "linux-x64"}]},
                }
            ]
        }
    )
    assert any("unsupported Aliyun Drive platform" in error for error in errors)
