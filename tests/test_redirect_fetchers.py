"""测试 make_redirect_fetcher 工厂以及它生产的 4 个具体 fetcher。"""

from __future__ import annotations

import re

from scripts.fetchers import nvidia_app, qq, wegame, yy
from scripts.fetchers._redirect import make_redirect_fetcher


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def test_factory_uses_today_as_version():
    fetch = make_redirect_fetcher(
        id="x", name="X", homepage="https://x/", download_page="https://x/dl"
    )
    result = fetch(
        {"platforms": [{"platform": "win-x64", "download_url": "https://x/a"}]}
    )

    assert _DATE_RE.match(result.version)
    assert result.id == "x"
    assert result.source == "Official download page; no public version API"


def test_factory_passes_through_yaml_urls():
    fetch = make_redirect_fetcher(
        id="x", name="X", homepage="https://x/", download_page="https://x/dl"
    )
    args = {
        "platforms": [
            {"platform": "win-x64", "download_url": "https://x/win.exe"},
            {"platform": "mac-universal", "download_url": "https://x/mac.dmg"},
        ]
    }

    result = fetch(args)

    urls = {a.platform: a.url for a in result.assets}
    assert urls == {
        "win-x64": "https://x/win.exe",
        "mac-universal": "https://x/mac.dmg",
    }


def test_factory_uses_download_page_when_platform_url_missing():
    fetch = make_redirect_fetcher(
        id="x", name="X", homepage="https://x/", download_page="https://x/dl"
    )

    result = fetch({"platforms": [{"platform": "win-x64"}]})

    assert result.assets[0].platform == "win-x64"
    assert result.assets[0].url == "https://x/dl"


def test_factory_falls_back_to_default_platform_when_empty():
    fetch = make_redirect_fetcher(
        id="x",
        name="X",
        homepage="https://x/",
        download_page="https://x/dl",
        default_platform="custom-platform",
    )

    result = fetch({})

    assert len(result.assets) == 1
    assert result.assets[0].platform == "custom-platform"
    assert result.assets[0].url == "https://x/dl"


def test_factory_custom_source_label():
    fetch = make_redirect_fetcher(
        id="x",
        name="X",
        homepage="https://x/",
        download_page="https://x/dl",
        source="自定义来源",
    )

    assert fetch({}).source == "自定义来源"


def test_qq_fetcher_metadata():
    result = qq.fetch({})
    assert result.id == "qq"
    assert result.name == "QQ"
    assert result.homepage == "https://im.qq.com/"
    assert result.notes_url == "https://im.qq.com/download/"


def test_yy_fetcher_metadata():
    result = yy.fetch({})
    assert result.id == "yy"
    assert result.name == "YY 语音"


def test_wegame_fetcher_id_is_wegame_not_empty():
    """重构前 wegame.id 是空串；重构后补全为 'wegame'。

    sync.py 会用 yaml 中的 id 覆盖，所以历史空串无害；
    但补全后单元测试 / 直接调用更可靠。
    """
    result = wegame.fetch({})
    assert result.id == "wegame"
    assert result.name == "WeGame"


def test_nvidia_app_fetcher_metadata():
    result = nvidia_app.fetch({})
    assert result.id == "nvidia-app"
    assert result.name == "NVIDIA App"
