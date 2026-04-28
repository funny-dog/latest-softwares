from __future__ import annotations

from scripts.fetchers import github_release


def test_tag_pattern_scans_configured_release_pages(monkeypatch):
    calls: list[str] = []

    def fake_get_json(url, **kwargs):
        calls.append(url)
        if "page=1" in url:
            return [
                {
                    "tag_name": "other-v9.9.9",
                    "prerelease": False,
                    "draft": False,
                    "assets": [],
                }
            ]
        return [
            {
                "tag_name": "desktop-v1.2.3",
                "prerelease": False,
                "draft": False,
                "published_at": "2026-01-02T00:00:00Z",
                "html_url": "https://github.com/acme/app/releases/tag/desktop-v1.2.3",
                "assets": [
                    {
                        "name": "AppSetup-1.2.3.exe",
                        "browser_download_url": "https://downloads.test/AppSetup.exe",
                        "size": 123,
                    }
                ],
            }
        ]

    monkeypatch.setattr(github_release, "get_json", fake_get_json)

    result = github_release.fetch(
        {
            "repo": "acme/app",
            "tag_pattern": "^desktop-v",
            "release_scan_pages": 2,
            "assets": [{"platform": "win-x64", "pattern": "AppSetup-*.exe"}],
        }
    )

    assert result.version == "1.2.3"
    assert len(result.assets) == 1
    assert calls == [
        "https://api.github.com/repos/acme/app/releases?per_page=30&page=1",
        "https://api.github.com/repos/acme/app/releases?per_page=30&page=2",
    ]


def test_empty_first_page_does_not_short_circuit_scan(monkeypatch):
    """GitHub /releases endpoint 偶发让 page=1 返回空数组，但 page=2 仍有数据。

    fetcher 必须继续扫剩余页，不能把"本页空"当成"分页结束"。
    """
    calls: list[str] = []

    def fake_get_json(url, **kwargs):
        calls.append(url)
        if "page=1" in url:
            return []  # 模拟 GitHub 边缘缓存抽风
        return [
            {
                "tag_name": "desktop-v9.9.9",
                "prerelease": False,
                "draft": False,
                "published_at": "2026-04-01T00:00:00Z",
                "html_url": "https://github.com/acme/app/releases/tag/desktop-v9.9.9",
                "assets": [
                    {
                        "name": "AppSetup-9.9.9.exe",
                        "browser_download_url": "https://downloads.test/AppSetup.exe",
                        "size": 1,
                    }
                ],
            }
        ]

    monkeypatch.setattr(github_release, "get_json", fake_get_json)

    result = github_release.fetch(
        {
            "repo": "acme/app",
            "tag_pattern": "^desktop-v",
            "release_scan_pages": 2,
            "assets": [{"platform": "win-x64", "pattern": "AppSetup-*.exe"}],
        }
    )

    assert result.version == "9.9.9"
    assert calls == [
        "https://api.github.com/repos/acme/app/releases?per_page=30&page=1",
        "https://api.github.com/repos/acme/app/releases?per_page=30&page=2",
    ]


def test_missing_github_assets_are_reported_as_warnings(monkeypatch):
    def fake_get_json(url, **kwargs):
        return {
            "tag_name": "v2.0.0",
            "published_at": "2026-01-02T00:00:00Z",
            "html_url": "https://github.com/acme/app/releases/tag/v2.0.0",
            "assets": [
                {
                    "name": "AppSetup-2.0.0.exe",
                    "browser_download_url": "https://downloads.test/AppSetup.exe",
                    "size": 456,
                }
            ],
        }

    monkeypatch.setattr(github_release, "get_json", fake_get_json)

    result = github_release.fetch(
        {
            "repo": "acme/app",
            "assets": [
                {"platform": "win-x64", "pattern": "AppSetup-*.exe"},
                {"platform": "mac-arm64", "pattern": "App-*.dmg"},
            ],
        }
    )

    assert [asset.platform for asset in result.assets] == ["win-x64"]
    assert result.warnings == [
        "mac-arm64: 没有匹配 asset pattern 'App-*.dmg'",
    ]
