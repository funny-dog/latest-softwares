from __future__ import annotations

import json

from scripts import sync
from scripts.fetchers import AssetInfo, FetchResult


def test_sync_rejects_invalid_config_before_writing(tmp_path, monkeypatch, capsys):
    packages_file = tmp_path / "packages.yaml"
    data_file = tmp_path / "latest.json"
    packages_file.write_text("packages: []\n", encoding="utf-8")

    monkeypatch.setattr(sync, "PACKAGES_FILE", packages_file)
    monkeypatch.setattr(sync, "DATA_FILE", data_file)

    rc = sync.main()

    assert rc == 1
    assert not data_file.exists()
    assert "packages.yaml 配置校验失败" in capsys.readouterr().err


def test_sync_records_stale_reason_and_failed_ids(tmp_path, monkeypatch):
    packages_file = tmp_path / "packages.yaml"
    data_file = tmp_path / "latest.json"
    packages_file.write_text(
        """
packages:
  - id: v2rayn
    name: v2rayN
    category: 网络代理
    fetcher: github_release
    args:
      repo: 2dust/v2rayN
      assets:
        - { platform: win-x64, pattern: "*.zip" }
""",
        encoding="utf-8",
    )
    data_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "packages": [
                    {
                        "id": "v2rayn",
                        "name": "v2rayN",
                        "version": "1.0.0",
                        "source": "previous",
                        "assets": [],
                        "fetched_at": "2026-01-01T00:00:00+00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def failing_fetcher(args):
        raise RuntimeError("temporary upstream failure")

    monkeypatch.setattr(sync, "PACKAGES_FILE", packages_file)
    monkeypatch.setattr(sync, "DATA_FILE", data_file)
    monkeypatch.setitem(sync.FETCHERS, "github_release", failing_fetcher)

    rc = sync.main()

    output = json.loads(data_file.read_text(encoding="utf-8"))
    stale_pkg = output["packages"][0]
    assert rc == 1
    assert output["stats"]["failed_ids"] == ["v2rayn"]
    assert output["stats"]["failures"] == [
        {"id": "v2rayn", "error": "temporary upstream failure"}
    ]
    assert stale_pkg["_stale"] is True
    assert stale_pkg["_stale_reason"] == "temporary upstream failure"
    assert stale_pkg["last_success_at"] == "2026-01-01T00:00:00+00:00"
    assert stale_pkg["fetched_at"] == "2026-01-01T00:00:00+00:00"
    assert stale_pkg["version_kind"] == "release_version"
    assert stale_pkg["version_source"] == "previous"


def test_sync_only_runs_selected_package(tmp_path, monkeypatch):
    packages_file = tmp_path / "packages.yaml"
    data_file = tmp_path / "latest.json"
    packages_file.write_text(
        """
packages:
  - id: one
    name: One
    category: 工具
    fetcher: github_release
    args:
      repo: example/one
      assets:
        - { platform: win-x64, pattern: "*.exe" }
  - id: two
    name: Two
    category: 工具
    fetcher: github_release
    args:
      repo: example/two
      assets:
        - { platform: win-x64, pattern: "*.exe" }
""",
        encoding="utf-8",
    )
    seen: list[str] = []

    def fake_fetcher(args):
        repo = args["repo"]
        seen.append(repo)
        name = repo.split("/")[-1].title()
        return FetchResult(
            id="",
            name=name,
            version="1.0.0",
            source=f"Fake Release: {repo}",
            assets=[AssetInfo(platform="win-x64", url=f"https://example.test/{name}")],
        )

    monkeypatch.setattr(sync, "PACKAGES_FILE", packages_file)
    monkeypatch.setattr(sync, "DATA_FILE", data_file)
    monkeypatch.setitem(sync.FETCHERS, "github_release", fake_fetcher)

    rc = sync.main(["--only", "two"])

    output = json.loads(data_file.read_text(encoding="utf-8"))
    assert rc == 0
    assert seen == ["example/two"]
    assert [pkg["id"] for pkg in output["packages"]] == ["two"]
    assert output["stats"]["total"] == 1


def test_sync_skip_omits_selected_package(tmp_path, monkeypatch):
    packages_file = tmp_path / "packages.yaml"
    data_file = tmp_path / "latest.json"
    packages_file.write_text(
        """
packages:
  - id: one
    name: One
    category: 工具
    fetcher: github_release
    args:
      repo: example/one
      assets:
        - { platform: win-x64, pattern: "*.exe" }
  - id: two
    name: Two
    category: 工具
    fetcher: github_release
    args:
      repo: example/two
      assets:
        - { platform: win-x64, pattern: "*.exe" }
""",
        encoding="utf-8",
    )
    seen: list[str] = []

    def fake_fetcher(args):
        repo = args["repo"]
        seen.append(repo)
        name = repo.split("/")[-1].title()
        return FetchResult(
            id="",
            name=name,
            version="1.0.0",
            source=f"Fake Release: {repo}",
            assets=[AssetInfo(platform="win-x64", url=f"https://example.test/{name}")],
        )

    monkeypatch.setattr(sync, "PACKAGES_FILE", packages_file)
    monkeypatch.setattr(sync, "DATA_FILE", data_file)
    monkeypatch.setitem(sync.FETCHERS, "github_release", fake_fetcher)

    rc = sync.main(["--skip", "one"])

    output = json.loads(data_file.read_text(encoding="utf-8"))
    assert rc == 0
    assert seen == ["example/two"]
    assert [pkg["id"] for pkg in output["packages"]] == ["two"]
    assert output["stats"]["total"] == 1
