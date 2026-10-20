"""离线验证修复结果贯穿覆盖门禁、README、两版前端与下载 API。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app_core.app_factory import create_app
from app_core.store import JsonFileMetricsStore
from scripts import build_web, render, validate_links
from scripts.merge_results import merge_results


def test_verified_snapshot_is_shared_by_both_editions_and_api(tmp_path, monkeypatch):
    entries = [
        {
            "id": "example",
            "name": "Example",
            "category": "Utilities",
            "homepage": "https://example.test/download",
            "fetcher": "github_release",
            "args": {
                "repo": "acme/example",
                "assets": [{"platform": "win-x64", "pattern": "*.exe"}],
            },
        },
        {
            "id": "other",
            "name": "Other",
            "category": "Utilities",
            "homepage": "https://other.test/download",
            "editions": ["intl"],
            "fetcher": "download_page",
            "args": {
                "platforms": [
                    {"platform": "mac", "download_url": "https://other.test/download"}
                ]
            },
        },
    ]
    old = {
        "id": "example",
        "name": "Example",
        "category": "Utilities",
        "version": "1.0",
        "source": "old",
        "version_kind": "release_version",
        "version_source": "old",
        "assets": [
            {"platform": "win-x64", "url": "https://example.test/old.exe", "size": 1}
        ],
    }
    candidate = merge_results(
        [{"packages": [old]}], {"removed": {"id": "removed"}}, entries
    )
    assert {p["id"] for p in candidate["packages"]} == {"example", "other"}
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(candidate))
    monkeypatch.setattr(validate_links, "DATA_FILE", path)
    monkeypatch.setattr(validate_links, "LINK_HEALTH_FILE", tmp_path / "health.json")
    monkeypatch.setattr(
        validate_links, "load_packages_config", lambda: {"packages": entries}
    )
    monkeypatch.setattr(
        validate_links,
        "load_baseline",
        lambda: {
            "required": [
                {"id": "example", "platforms": ["win-x64"], "editions": ["cn", "intl"]}
            ]
        },
    )

    def verify(asset, config, **kwargs):
        return (
            {"status": "failed", "checked_at": datetime.now(timezone.utc).isoformat()}
            if asset["url"].endswith("old.exe")
            else {
                "status": "verified",
                "url": asset["url"],
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "valid_until": (
                    datetime.now(timezone.utc) + timedelta(days=1)
                ).isoformat(),
            }
        )

    monkeypatch.setattr(validate_links, "verify_link", verify)
    fresh = {
        **old,
        "version": "2.0",
        "assets": [
            {"platform": "win-x64", "url": "https://example.test/new.exe", "size": 200}
        ],
    }
    monkeypatch.setattr(
        validate_links,
        "_refetch_package",
        lambda config: fresh if config["id"] == "example" else None,
    )
    assert validate_links.validate_and_fix(gate=True) == 0
    verified = json.loads(path.read_text())
    assert verified["quality"]["required_covered"] == 1
    assert verified["packages"][0]["version"] == "2.0"
    markdown = render.render_markdown(verified, render.README_EN[0])
    assert "https://example.test/new.exe" in markdown and "old.exe" not in markdown
    assert "removed" not in markdown
    monkeypatch.setattr(build_web, "DATA_FILE", path)
    monkeypatch.setattr(
        build_web, "load_packages_config", lambda: {"packages": entries}
    )
    monkeypatch.setattr(build_web, "DIST", tmp_path)
    template = (build_web.WEB_SRC / "index.html").read_text()
    for edition, count in [("cn", 1), ("intl", 2)]:
        (tmp_path / "index.html").write_text(template)
        assert build_web.inject_data(edition) == count
        html = (tmp_path / "index.html").read_text()
        assert (
            verified["release_id"] in html
            and "new.exe" in html
            and "old.exe" not in html
        )
        client = TestClient(
            create_app(
                edition=edition,
                store=JsonFileMetricsStore(tmp_path / f"{edition}.json"),
                data_file=path,
            )
        )
        assert client.get("/api/health").json()["release_id"] == verified["release_id"]
        response = client.get("/api/download/example/win-x64", follow_redirects=False)
        assert response.headers["location"] == "https://example.test/new.exe"
