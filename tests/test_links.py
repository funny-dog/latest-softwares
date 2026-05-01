from __future__ import annotations

import json

from scripts import link_health_summary, link_utils, validate_links
from scripts.fetchers.base import AssetInfo, FetchResult


def test_direct_link_detection_uses_shared_extensions():
    assert link_utils.is_direct_link("https://example.test/app.exe?token=1")
    assert link_utils.is_direct_link("https://example.test/app.tar.gz")
    assert not link_utils.is_direct_link("https://example.test/download/")


def test_explicit_link_kind_overrides_extension_heuristic():
    assert link_utils.is_direct_link(
        "https://example.test/download",
        link_kind=link_utils.LINK_KIND_DIRECT,
    )
    assert not link_utils.is_direct_link(
        "https://example.test/app.exe",
        link_kind=link_utils.LINK_KIND_LANDING_PAGE,
    )


def test_refetch_repair_uses_registered_fetcher(monkeypatch):
    calls: list[dict] = []

    def fake_fetcher(args):
        calls.append(args)
        return FetchResult(
            id="",
            name="Example",
            version="2.0",
            source="test",
            assets=[
                AssetInfo(platform="win-x64", url="https://example.test/new.exe"),
                AssetInfo(platform="mac-arm64", url="https://example.test/new.dmg"),
            ],
        )

    monkeypatch.setitem(validate_links.FETCHERS, "github_release", fake_fetcher)

    fixed_url = validate_links._fix_by_refetch(
        {
            "id": "example",
            "fetcher": "github_release",
            "args": {"repo": "owner/repo", "assets": []},
        },
        {"platform": "mac-arm64", "url": "https://example.test/old.dmg"},
    )

    assert fixed_url == "https://example.test/new.dmg"
    assert calls == [{"repo": "owner/repo", "assets": []}]


def test_validate_links_writes_structured_health_report(tmp_path, monkeypatch):
    data_file = tmp_path / "latest.json"
    packages_file = tmp_path / "packages.yaml"
    health_file = tmp_path / "link-health.json"
    data_file.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "generated_at": "2026-01-02T03:04:05+00:00",
                "packages": [
                    {
                        "id": "example",
                        "name": "Example",
                        "category": "工具",
                        "version": "1.0.0",
                        "version_kind": "release_version",
                        "version_source": "test",
                        "source": "test",
                        "fetched_at": "2026-01-02T03:04:05+00:00",
                        "assets": [
                            {
                                "platform": "win-x64",
                                "url": "https://example.test/app.exe",
                            },
                            {
                                "platform": "web",
                                "url": "https://example.test/download/",
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    packages_file.write_text(
        """
packages:
  - id: example
    name: Example
    category: 工具
    fetcher: github_release
    args:
      repo: owner/repo
      assets:
        - { platform: win-x64, pattern: "*.exe" }
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(validate_links, "DATA_FILE", data_file)
    monkeypatch.setattr(
        "scripts.config_loader.PACKAGES_DIR", tmp_path / "nonexistent_packages_dir"
    )
    monkeypatch.setattr("scripts.config_loader.PACKAGES_FILE", packages_file)
    monkeypatch.setattr(validate_links, "LINK_HEALTH_FILE", health_file)
    monkeypatch.setattr(validate_links, "_check_url_robust", lambda url: True)

    rc = validate_links.validate_and_fix()

    report = json.loads(health_file.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["schema_version"] == 1
    assert report["stats"] == {
        "total": 2,
        "direct": 1,
        "landing_page": 1,
        "ok": 1,
        "fixed": 0,
        "failed": 0,
    }
    rows = sorted(report["links"], key=lambda item: item["platform"])
    assert rows == [
        {
            "id": "example",
            "platform": "web",
            "kind": "landing_page",
            "status": "skipped",
            "url": "https://example.test/download/",
        },
        {
            "id": "example",
            "platform": "win-x64",
            "kind": "direct",
            "status": "ok",
            "url": "https://example.test/app.exe",
        },
    ]


def test_link_health_summary_writes_github_step_summary(tmp_path, monkeypatch):
    report = tmp_path / "link-health.json"
    summary = tmp_path / "summary.md"
    report.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-01-02T03:04:05+00:00",
                "stats": {
                    "total": 2,
                    "direct": 1,
                    "landing_page": 1,
                    "ok": 0,
                    "fixed": 0,
                    "failed": 1,
                },
                "links": [
                    {
                        "id": "example",
                        "platform": "win-x64",
                        "kind": "direct",
                        "status": "failed",
                        "url": "https://example.test/app.exe",
                        "error": "无法自动修复",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    rc = link_health_summary.main([str(report)])

    text = summary.read_text(encoding="utf-8")
    assert rc == 0
    assert "Link Health" in text
    assert "| Total | Direct | Landing pages | OK | Fixed | Failed |" in text
    assert "| `example` | `win-x64` | `direct` | `failed` |" in text
