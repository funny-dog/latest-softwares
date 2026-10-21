from __future__ import annotations

import json

import pytest

from app_core.downloads import asset_available
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
    monkeypatch.setattr(
        validate_links,
        "verify_link",
        lambda asset, config, **kwargs: {
            "status": "verified",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )

    rc = validate_links.validate_and_fix()

    report = json.loads(health_file.read_text(encoding="utf-8"))
    assert rc == 0
    assert report["schema_version"] == 2
    assert report["stats"]["total"] == 2
    assert report["stats"]["ok"] == 2
    assert report["stats"]["failed"] == 0
    rows = sorted(report["links"], key=lambda item: item["platform"])
    assert [row["status"] for row in rows] == ["ok", "ok"]
    assert {row["kind"] for row in rows} == {"direct", "landing_page"}


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


def _setup_validation(tmp_path, monkeypatch, required=True, platforms=("win-x64",)):
    data_file = tmp_path / "latest.json"
    config = {
        "id": "example",
        "name": "Example",
        "category": "Utilities",
        "fetcher": "github_release",
        "args": {
            "repo": "owner/repo",
            "assets": [{"platform": p, "pattern": "*.exe"} for p in platforms],
        },
    }
    package = {
        "id": "example",
        "name": "Example",
        "version": "1.0",
        "version_kind": "release_version",
        "source": "old",
        "assets": [
            {
                "platform": p,
                "url": f"https://example.test/old-{p}.exe",
                "filename": "old.exe",
                "size": 1,
            }
            for p in platforms
        ],
    }
    data_file.write_text(json.dumps({"schema_version": 2, "packages": [package]}))
    monkeypatch.setattr(validate_links, "DATA_FILE", data_file)
    monkeypatch.setattr(
        validate_links, "LINK_HEALTH_FILE", tmp_path / "link-health.json"
    )
    monkeypatch.setattr(
        validate_links, "load_packages_config", lambda: {"packages": [config]}
    )
    monkeypatch.setattr(
        validate_links,
        "load_baseline",
        lambda: {
            "required": [{"id": "example", "platforms": list(platforms)}]
            if required
            else []
        },
    )
    return data_file, config


def _verified(**extra):
    return {
        "status": "verified",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "valid_until": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        **extra,
    }


def test_repaired_release_is_reverified_and_replaces_all_metadata(
    tmp_path, monkeypatch
):
    path, _ = _setup_validation(tmp_path, monkeypatch)
    seen = []

    def verify(asset, config, **kwargs):
        seen.append(asset["url"])
        return (
            _verified()
            if "new" in asset["url"]
            else {
                "status": "failed",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    monkeypatch.setattr(validate_links, "verify_link", verify)
    monkeypatch.setattr(
        validate_links,
        "_refetch_package",
        lambda c: {
            "id": "example",
            "name": "Example",
            "version": "2.0",
            "source": "new",
            "assets": [
                {
                    "platform": "win-x64",
                    "url": "https://example.test/new.exe",
                    "filename": "new.exe",
                    "size": 200,
                }
            ],
        },
    )
    assert validate_links.validate_and_fix(gate=True) == 0
    package = json.loads(path.read_text())["packages"][0]
    assert package["version"] == "2.0"
    assert package["assets"][0]["size"] == 200
    assert seen == [
        "https://example.test/old-win-x64.exe",
        "https://example.test/new.exe",
    ]
    assert (
        json.loads((tmp_path / "link-health.json").read_text())["stats"]["fixed"] == 1
    )


def test_unverified_repair_is_not_published_as_fixed(tmp_path, monkeypatch):
    path, _ = _setup_validation(tmp_path, monkeypatch)
    monkeypatch.setattr(
        validate_links,
        "verify_link",
        lambda *a, **kw: {
            "status": "failed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "reason": "bad file",
        },
    )
    monkeypatch.setattr(
        validate_links,
        "_refetch_package",
        lambda c: {
            "id": "example",
            "version": "2.0",
            "assets": [{"platform": "win-x64", "url": "https://example.test/new.exe"}],
        },
    )
    assert validate_links.validate_and_fix(gate=True) == 1
    assert json.loads(path.read_text())["packages"][0]["version"] == "1.0"
    assert (
        json.loads((tmp_path / "link-health.json").read_text())["stats"]["fixed"] == 0
    )


def test_incremental_cache_avoids_repeated_http_and_preserves_history(
    tmp_path, monkeypatch
):
    _setup_validation(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        validate_links, "verify_link", lambda *a, **kw: calls.append(1) or _verified()
    )
    assert validate_links.validate_and_fix(gate=True) == 0
    assert validate_links.validate_and_fix(gate=True) == 0
    assert calls == [1]
    state = json.loads((tmp_path / "link-state.json").read_text())["assets"][
        "example:win-x64"
    ]
    assert len(state["history"]) == 1
    assert state["last_success_at"]


def test_maintenance_page_keeps_previous_verification_and_retries_soon(
    tmp_path, monkeypatch
):
    """上游整站维护期间沿用仍未过期的旧验证，不延长有效期、且尽快重试。"""
    path, _ = _setup_validation(tmp_path, monkeypatch)
    monkeypatch.setattr(validate_links, "verify_link", lambda *a, **kw: _verified())
    assert validate_links.validate_and_fix(gate=True) == 0
    published = json.loads(path.read_text())["packages"][0]["assets"][0]
    original_valid_until = published["verification"]["valid_until"]

    # 第二轮：上游整站维护，直链与官网都只返回维护页
    monkeypatch.setattr(
        validate_links,
        "_refetch_package",
        lambda c: {
            "id": "example",
            "version": "1.0",
            "assets": [{"platform": "win-x64", "url": "https://example.test/a.exe"}],
        },
    )
    monkeypatch.setattr(
        validate_links,
        "verify_link",
        lambda *a, **kw: {
            "status": "transient",
            "reason": "upstream maintenance page",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert validate_links.validate_and_fix(gate=True, force=True) == 0

    asset = json.loads(path.read_text())["packages"][0]["assets"][0]
    # 入口没有被替换成维护页，下载仍指向原地址
    assert asset["url"] == "https://example.test/old-win-x64.exe"
    # 沿用旧验证，且没有延长有效期
    assert asset["verification"]["status"] == "verified"
    assert asset["verification"]["valid_until"] == original_valid_until
    # 记录本次尝试，便于排查
    assert asset["verification"]["last_attempt_status"] == "transient"
    state = json.loads((tmp_path / "link-state.json").read_text())["assets"][
        "example:win-x64"
    ]
    assert state["history"][-1]["status"] == "transient"
    next_check = datetime.fromisoformat(state["next_check_at"])
    assert next_check <= datetime.now(timezone.utc) + timedelta(
        minutes=validate_links.MAINTENANCE_RETRY_MINUTES
    )


def test_maintenance_page_does_not_resurrect_expired_verification(
    tmp_path, monkeypatch
):
    """旧验证已过期时，维护页不能把入口重新变成可用——那是真失效。"""
    path, _ = _setup_validation(tmp_path, monkeypatch)
    monkeypatch.setattr(validate_links, "verify_link", lambda *a, **kw: _verified())
    assert validate_links.validate_and_fix(gate=True) == 0

    # 让 state 与快照中的验证都过期，模拟上游宕机超过 7 天
    expired = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    state_path = tmp_path / "link-state.json"
    state = json.loads(state_path.read_text())
    entry = state["assets"]["example:win-x64"]
    entry["verification"]["valid_until"] = expired
    entry["next_check_at"] = expired
    # 历史里的成功记录同样超出 7 天，确保自愈逻辑不会把它救回来
    entry["last_success_at"] = expired
    entry["history"] = [{**h, "at": expired} for h in entry.get("history", [])]
    state_path.write_text(json.dumps(state))
    data = json.loads(path.read_text())
    data["packages"][0]["assets"][0]["verification"]["valid_until"] = expired
    path.write_text(json.dumps(data))

    monkeypatch.setattr(
        validate_links,
        "_refetch_package",
        lambda c: {
            "id": "example",
            "version": "1.0",
            "assets": [{"platform": "win-x64", "url": "https://example.test/a.exe"}],
        },
    )
    monkeypatch.setattr(
        validate_links,
        "verify_link",
        lambda *a, **kw: {
            "status": "transient",
            "reason": "upstream maintenance page",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert validate_links.validate_and_fix(gate=True, force=True) == 1

    asset = json.loads(path.read_text())["packages"][0]["assets"][0]
    assert asset["verification"]["status"] == "transient"
    assert not asset_available(asset)


def test_maintenance_page_without_link_state_falls_back_to_snapshot(
    tmp_path, monkeypatch
):
    """link-state 缓存丢失时，回退到快照自身仍有效的验证，不能让 cache miss 阻塞发布。"""
    path, _ = _setup_validation(tmp_path, monkeypatch)
    monkeypatch.setattr(validate_links, "verify_link", lambda *a, **kw: _verified())
    assert validate_links.validate_and_fix(gate=True) == 0
    published_until = json.loads(path.read_text())["packages"][0]["assets"][0][
        "verification"
    ]["valid_until"]

    # 模拟 Actions cache 未命中：只有快照，没有 link-state.json
    (tmp_path / "link-state.json").unlink()
    monkeypatch.setattr(
        validate_links,
        "_refetch_package",
        lambda c: {
            "id": "example",
            "version": "1.0",
            "assets": [{"platform": "win-x64", "url": "https://example.test/a.exe"}],
        },
    )
    monkeypatch.setattr(
        validate_links,
        "verify_link",
        lambda *a, **kw: {
            "status": "transient",
            "reason": "upstream maintenance page",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert validate_links.validate_and_fix(gate=True, force=True) == 0

    asset = json.loads(path.read_text())["packages"][0]["assets"][0]
    assert asset["verification"]["status"] == "verified"
    assert asset["verification"]["last_attempt_status"] == "transient"
    assert asset["verification"]["valid_until"] == published_until


def test_carry_over_drops_stale_transient_markers(tmp_path, monkeypatch):
    """回退沿用旧验证时，必须用本轮尝试覆盖上一轮残留的 last_attempt_* 标记。"""
    path, _ = _setup_validation(tmp_path, monkeypatch)
    monkeypatch.setattr(validate_links, "verify_link", lambda *a, **kw: _verified())
    assert validate_links.validate_and_fix(gate=True) == 0

    published = json.loads(path.read_text())["packages"][0]["assets"][0]
    published_until = published["verification"]["valid_until"]
    published["verification"]["last_attempt_status"] = "transient"
    published["verification"]["last_attempt_reason"] = "stale reason"
    data = json.loads(path.read_text())
    data["packages"][0]["assets"][0] = published
    path.write_text(json.dumps(data))
    (tmp_path / "link-state.json").unlink()

    monkeypatch.setattr(validate_links, "_refetch_package", lambda c: None)
    monkeypatch.setattr(
        validate_links,
        "verify_link",
        lambda *a, **kw: {
            "status": "transient",
            "reason": "upstream maintenance page",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert validate_links.validate_and_fix(gate=True, force=True) == 0

    verification = json.loads(path.read_text())["packages"][0]["assets"][0][
        "verification"
    ]
    assert verification["status"] == "verified"
    assert verification["last_attempt_status"] == "transient"
    assert verification["last_attempt_reason"] == "upstream maintenance page"
    assert verification["valid_until"] == published_until


def test_budget_exhaustion_blocks_missing_critical_platform(tmp_path, monkeypatch):
    _setup_validation(tmp_path, monkeypatch, platforms=("win-x64", "mac-arm64"))
    calls = []
    monkeypatch.setattr(
        validate_links, "verify_link", lambda *a, **kw: calls.append(1) or _verified()
    )
    assert validate_links.validate_and_fix(gate=True, budget=1) == 1
    assert calls == [1]
    assert (
        json.loads((tmp_path / "link-health.json").read_text())["stats"]["deferred"]
        == 1
    )


def test_verified_official_page_fallback_is_recorded(tmp_path, monkeypatch):
    path, config = _setup_validation(tmp_path, monkeypatch)
    config["homepage"] = "https://example.test/download"
    monkeypatch.setattr(validate_links, "_refetch_package", lambda c: None)
    monkeypatch.setattr(
        validate_links,
        "verify_link",
        lambda a, c, **kw: (
            _verified()
            if a["url"] == config["homepage"]
            else {
                "status": "restricted",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
    )
    assert validate_links.validate_and_fix(gate=True) == 0
    asset = json.loads(path.read_text())["packages"][0]["assets"][0]
    assert asset["url"] == config["homepage"]
    assert asset["link_kind"] == "landing_page" and asset["fallback"]


def test_validate_links_raises_per_host_connection_limit(tmp_path, monkeypatch):
    _setup_validation(tmp_path, monkeypatch)
    limits = []
    monkeypatch.setattr(validate_links, "set_max_connections_per_host", limits.append)
    monkeypatch.setattr(validate_links, "verify_link", lambda *a, **kw: _verified())
    validate_links.validate_and_fix()
    assert limits == [validate_links.MAX_CONNECTIONS_PER_HOST]
    assert validate_links.MAX_CONNECTIONS_PER_HOST >= validate_links.MAX_WORKERS


def test_explicit_exception_preserves_unavailable_asset_and_does_not_persist(
    tmp_path, monkeypatch
):
    path, _ = _setup_validation(tmp_path, monkeypatch)
    monkeypatch.setenv("GITHUB_ACTOR", "reviewer")
    monkeypatch.setattr(validate_links, "_refetch_package", lambda c: None)
    monkeypatch.setattr(
        validate_links,
        "verify_link",
        lambda *a, **kw: {
            "status": "restricted",
            "reason": "HTTP 403",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert (
        validate_links.validate_and_fix(
            gate=True,
            allow_unverified_required={"example"},
            exception_reason="User approved disabled entry",
        )
        == 0
    )
    data = json.loads(path.read_text())
    assert data["quality"]["required_covered"] == 0
    assert data["quality"]["publication_exceptions"][0]["approved_by"] == "reviewer"
    assert not asset_available(data["packages"][0]["assets"][0])
    report = json.loads((tmp_path / "coverage-report.json").read_text())
    assert report["gate_errors"] == []
    assert report["strict_gate_errors"] == ["example"]
    assert validate_links.validate_and_fix(gate=True) == 1
    assert json.loads(path.read_text())["quality"]["publication_exceptions"] == []


def test_exception_cannot_waive_missing_software_or_platform(tmp_path, monkeypatch):
    path, _ = _setup_validation(tmp_path, monkeypatch)
    data = json.loads(path.read_text())
    data["packages"][0]["assets"] = []
    path.write_text(json.dumps(data))
    assert (
        validate_links.validate_and_fix(
            gate=True,
            allow_unverified_required={"example"},
            exception_reason="User approval",
        )
        == 1
    )
    assert json.loads(path.read_text())["quality"]["publication_exceptions"] == []


def test_exception_requires_reason_gate_and_known_required_id(tmp_path, monkeypatch):
    _setup_validation(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="reason"):
        validate_links.validate_and_fix(
            gate=True, allow_unverified_required={"example"}
        )
    with pytest.raises(ValueError, match="--gate"):
        validate_links.validate_and_fix(
            allow_unverified_required={"example"}, exception_reason="Approval"
        )
    with pytest.raises(ValueError, match="required software"):
        validate_links.validate_and_fix(
            gate=True,
            allow_unverified_required={"unknown"},
            exception_reason="Approval",
        )


def _write_polluted_state(tmp_path, *, history, last_success):
    """构造已被旧版本污染的 link-state：失败记录替代了原验证结果。"""
    url = "https://example.test/old-win-x64.exe"
    config = {
        "id": "example",
        "name": "Example",
        "fetcher": "package_manifest",
        "args": {
            "provider": "brew",
            "package": "example",
            "platforms": [{"platform": "win-x64"}],
        },
    }
    fingerprint = validate_links._config_fingerprint(
        config, {"platform": "win-x64", "url": url}
    )
    (tmp_path / "link-state.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "assets": {
                    "example:win-x64": {
                        "fingerprint": fingerprint,
                        "verification": {
                            "status": "failed",
                            "checked_at": "2026-10-21T17:00:00+00:00",
                            "reason": "expected installer",
                        },
                        "failures": 1,
                        "next_check_at": "2026-10-21T19:00:00+00:00",
                        "last_success_at": last_success,
                        "history": history,
                    }
                },
            }
        )
    )


@pytest.mark.parametrize(
    "history,last_success,status,expected",
    [
        # 历史里有同 URL 的成功记录 + 本轮是临时故障 → 自愈放行
        ("recent", "recent", "transient", 0),
        # 本轮是真失效（404）→ 不放行
        ("recent", "recent", "failed", 1),
        # 没有任何成功记录 → 不放行
        ([], None, "transient", 1),
        # 最近成功已超出 7 天 → 不放行
        ([], "stale", "transient", 1),
        # 成功记录是别的 URL → 不放行
        ("other_url", None, "transient", 1),
    ],
)
def test_polluted_state_self_heals_only_for_transient_failures(
    tmp_path, monkeypatch, history, last_success, status, expected
):
    """缓存被旧版本写成 failed 后，只允许凭历史成功记录为临时故障自愈。"""
    _, config = _setup_validation(tmp_path, monkeypatch)
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=3)).isoformat(timespec="seconds")
    if history == "recent":
        history = [
            {
                "at": recent,
                "url": "https://example.test/old-win-x64.exe",
                "status": "verified",
                "reason": None,
            }
        ]
    elif history == "other_url":
        history = [
            {
                "at": recent,
                "url": "https://example.test/old-win-mac.dmg",
                "status": "verified",
                "reason": None,
            }
        ]
    if last_success == "recent":
        last_success = recent
    elif last_success == "stale":
        last_success = (now - timedelta(days=8)).isoformat(timespec="seconds")
    _write_polluted_state(tmp_path, history=history, last_success=last_success)

    monkeypatch.setattr(validate_links, "_refetch_package", lambda c: None)
    monkeypatch.setattr(
        validate_links,
        "verify_link",
        lambda a, c, **kw: {
            "status": status,
            "reason": (
                "upstream maintenance page" if status == "transient" else "HTTP 404"
            ),
            "checked_at": now.isoformat(timespec="seconds"),
        },
    )
    assert validate_links.validate_and_fix(gate=True, force=True) == expected
