from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

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


def _setup_validate_env(tmp_path, monkeypatch, *, version="1.0.0"):
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
                        "version": version,
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
    # 避免修改 net 模块的全局并发上限而影响其它测试
    monkeypatch.setattr(validate_links, "set_max_connections_per_host", lambda _: None)
    checked: list[str] = []

    def fake_check(url):
        checked.append(url)
        return True

    monkeypatch.setattr(validate_links, "_check_url_robust", fake_check)
    return health_file, checked


def _write_previous_report(health_file, *, version, checked_at, status="ok"):
    health_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "links": [
                    {
                        "id": "example",
                        "platform": "win-x64",
                        "kind": "direct",
                        "status": status,
                        "url": "https://example.test/app.exe",
                        "version": version,
                        "checked_at": checked_at,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _iso_days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(
        timespec="seconds"
    )


def test_validate_links_writes_structured_health_report(tmp_path, monkeypatch):
    health_file, checked = _setup_validate_env(tmp_path, monkeypatch)

    rc = validate_links.validate_and_fix()

    report = json.loads(health_file.read_text(encoding="utf-8"))
    assert rc == 0
    assert checked == ["https://example.test/app.exe"]
    assert report["schema_version"] == 1
    assert report["stats"] == {
        "total": 2,
        "direct": 1,
        "landing_page": 1,
        "ok": 1,
        "fixed": 0,
        "failed": 0,
        "cached": 0,
    }
    rows = sorted(report["links"], key=lambda item: item["platform"])
    assert rows[0] == {
        "id": "example",
        "platform": "web",
        "kind": "landing_page",
        "status": "skipped",
        "url": "https://example.test/download/",
    }
    direct = rows[1]
    assert datetime.fromisoformat(direct.pop("checked_at"))
    assert direct == {
        "id": "example",
        "platform": "win-x64",
        "kind": "direct",
        "status": "ok",
        "url": "https://example.test/app.exe",
        "version": "1.0.0",
    }


def test_validate_links_reuses_recent_ok_result_for_same_version(tmp_path, monkeypatch):
    health_file, checked = _setup_validate_env(tmp_path, monkeypatch)
    previous_at = _iso_days_ago(1)
    _write_previous_report(health_file, version="1.0.0", checked_at=previous_at)

    rc = validate_links.validate_and_fix()

    report = json.loads(health_file.read_text(encoding="utf-8"))
    assert rc == 0
    assert checked == []
    assert report["stats"]["ok"] == 1
    assert report["stats"]["cached"] == 1
    direct = next(row for row in report["links"] if row["kind"] == "direct")
    # 沿用原 checked_at，TTL 从首次真实校验起算，而不是每次续期
    assert direct["checked_at"] == previous_at


def test_validate_links_rechecks_when_version_changed(tmp_path, monkeypatch):
    health_file, checked = _setup_validate_env(tmp_path, monkeypatch, version="2.0.0")
    _write_previous_report(health_file, version="1.0.0", checked_at=_iso_days_ago(1))

    validate_links.validate_and_fix()

    assert checked == ["https://example.test/app.exe"]


def test_validate_links_rechecks_expired_or_failed_results(tmp_path, monkeypatch):
    health_file, checked = _setup_validate_env(tmp_path, monkeypatch)

    _write_previous_report(health_file, version="1.0.0", checked_at=_iso_days_ago(8))
    validate_links.validate_and_fix(max_age_days=7)
    assert checked == ["https://example.test/app.exe"]

    checked.clear()
    _write_previous_report(
        health_file, version="1.0.0", checked_at=_iso_days_ago(1), status="failed"
    )
    validate_links.validate_and_fix()
    assert checked == ["https://example.test/app.exe"]


def test_validate_links_full_ignores_previous_report(tmp_path, monkeypatch):
    health_file, checked = _setup_validate_env(tmp_path, monkeypatch)
    _write_previous_report(health_file, version="1.0.0", checked_at=_iso_days_ago(1))

    validate_links.main(["--full"])

    assert checked == ["https://example.test/app.exe"]


def test_validate_links_raises_per_host_connection_limit(tmp_path, monkeypatch):
    _setup_validate_env(tmp_path, monkeypatch)
    limits: list[int] = []
    monkeypatch.setattr(validate_links, "set_max_connections_per_host", limits.append)

    validate_links.validate_and_fix()

    assert limits == [validate_links.MAX_CONNECTIONS_PER_HOST]
    assert validate_links.MAX_CONNECTIONS_PER_HOST >= validate_links.MAX_WORKERS


def test_validate_links_leaves_data_untouched_without_fixes(tmp_path, monkeypatch):
    _setup_validate_env(tmp_path, monkeypatch)
    data_file = validate_links.DATA_FILE
    original = data_file.read_text(encoding="utf-8")
    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    validate_links.validate_and_fix()

    assert data_file.read_text(encoding="utf-8") == original
    assert output.read_text(encoding="utf-8") == "fixed=0\nfailed=0\n"


def test_validate_links_writes_fixed_url_and_reports_output(tmp_path, monkeypatch):
    _setup_validate_env(tmp_path, monkeypatch)
    monkeypatch.setattr(validate_links, "_check_url_robust", lambda url: False)
    monkeypatch.setattr(
        validate_links,
        "_fix_by_refetch",
        lambda config, asset: "https://example.test/app-v2.exe",
    )
    output = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    rc = validate_links.validate_and_fix()

    data = json.loads(validate_links.DATA_FILE.read_text(encoding="utf-8"))
    urls = [a["url"] for a in data["packages"][0]["assets"]]
    assert rc == 0
    assert "https://example.test/app-v2.exe" in urls
    assert output.read_text(encoding="utf-8") == "fixed=1\nfailed=0\n"


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
                    "cached": 0,
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
    assert "| Total | Direct | Landing pages | OK | Fixed | Failed | Cached |" in text
    assert "| `example` | `win-x64` | `direct` | `failed` |" in text
