from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts.catalog import (
    coverage_report,
    expected_platforms,
    fallback_record,
    load_baseline,
)
from scripts.config_loader import load_packages_config
from scripts.merge_results import merge_results
from scripts.schedule import next_sync, sync_due

ENTRY = {
    "id": "example",
    "name": "Example",
    "category": "Utilities",
    "homepage": "https://example.test/download",
    "fetcher": "github_release",
    "args": {
        "repo": "owner/example",
        "assets": [{"platform": "win-x64", "pattern": "*.exe"}],
    },
}


def test_merge_follows_current_catalog_and_recovers_new_missing_entries():
    old = {"removed": {"id": "removed", "assets": []}}
    result = merge_results([{"packages": []}], old, [ENTRY])
    assert [p["id"] for p in result["packages"]] == ["example"]
    record = result["packages"][0]
    assert record["_stale"]
    assert record["version_kind"] == "sync_date"
    assert record["assets"][0]["url"] == ENTRY["homepage"]
    assert record["assets"][0]["verification"]["status"] == "unverified"


def test_targeted_merge_only_marks_missing_scheduled_packages_stale():
    previous = {
        pid: {"id": pid, "version": "1.0"} for pid in ("updated", "skipped", "missing")
    }
    result = merge_results(
        [{"packages": [previous["updated"]]}],
        previous,
        scheduled_ids={"updated", "missing"},
    )
    records = {p["id"]: p for p in result["packages"]}
    assert records["skipped"] == previous["skipped"]
    assert records["missing"]["_stale"]
    assert result["stats"]["failed_ids"] == ["missing"]


def test_coverage_reports_catalog_data_platform_and_verification_gaps():
    now = datetime.now(timezone.utc)
    baseline = {
        "required": [
            {
                "id": "example",
                "platforms": ["win-x64", "mac-arm64"],
                "editions": ["cn", "intl"],
            },
            {"id": "missing"},
        ]
    }
    data = {
        "packages": [
            {
                "id": "example",
                "assets": [
                    {
                        "platform": "win-x64",
                        "url": ENTRY["homepage"],
                        "verification": {
                            "status": "verified",
                            "valid_until": (now + timedelta(days=1)).isoformat(),
                        },
                    }
                ],
            }
        ]
    }
    report = coverage_report([ENTRY], data, baseline, now=now)
    assert report["gate_errors"] == ["example", "missing"]
    assert report["required_covered"] == 0
    assert "missing_platform:mac-arm64" in report["problems"][0]["issues"]
    data["packages"][0]["assets"].append(
        {**data["packages"][0]["assets"][0], "platform": "mac-arm64"}
    )
    assert (
        coverage_report([ENTRY], data, {"required": baseline["required"][:1]}, now=now)[
            "required_covered"
        ]
        == 1
    )


def test_exemption_unblocks_only_restricted_upstream():
    """长期例外只该放行"上游拒绝访问"，真实失效仍必须阻塞发布。"""
    now = datetime.now(timezone.utc)
    baseline = {
        "required": [
            {
                "id": "example",
                "platforms": ["win-x64"],
                "editions": ["cn", "intl"],
                "exemptions": {"reason": "上游 403", "review_by": "2027-01-01"},
            }
        ]
    }

    def build(status, valid_until=None):
        return {
            "packages": [
                {
                    "id": "example",
                    "assets": [
                        {
                            "platform": "win-x64",
                            "url": ENTRY["homepage"],
                            "verification": {
                                "status": status,
                                "valid_until": (
                                    valid_until or (now + timedelta(days=1))
                                ).isoformat(),
                            },
                        }
                    ],
                }
            ]
        }

    # restricted（反爬/限流）→ 豁免，不再阻塞
    report = coverage_report([ENTRY], build("restricted"), baseline, now=now)
    assert report["gate_errors"] == []
    assert [e["id"] for e in report["required_exemptions"]] == ["example"]

    # failed（404 等真实失效）→ 仍然阻塞，不能被豁免
    report = coverage_report([ENTRY], build("failed"), baseline, now=now)
    assert report["gate_errors"] == ["example"]
    assert report["required_exemptions"] == []

    # 过期的例外不再生效
    expired = {
        "required": [
            {
                "id": "example",
                "platforms": ["win-x64"],
                "editions": ["cn", "intl"],
                "exemptions": {"reason": "上游 403", "review_by": "2020-01-01"},
            }
        ]
    }
    report = coverage_report([ENTRY], build("restricted"), expired, now=now)
    assert report["gate_errors"] == ["example"]

    # 没有配置例外时，restricted 照旧阻塞
    no_exemption = {
        "required": [
            {
                "id": "example",
                "platforms": ["win-x64"],
                "editions": ["cn", "intl"],
            }
        ]
    }
    report = coverage_report([ENTRY], build("restricted"), no_exemption, now=now)
    assert report["gate_errors"] == ["example"]


def test_committed_baseline_is_unique_and_all_required_platforms_are_configured():
    baseline = load_baseline()["required"]
    config = {p["id"]: p for p in load_packages_config()["packages"]}
    assert len({p["id"] for p in baseline}) == len(baseline) >= 90
    for requirement in baseline:
        assert requirement["id"] in config
        assert set(requirement["platforms"]) <= set(
            expected_platforms(config[requirement["id"]])
        )


def test_new_package_fallback_does_not_pretend_to_know_release_version():
    result = fallback_record(ENTRY, "source failed")
    assert result["_stale"]
    assert result["version_kind"] == "sync_date"
    assert all(a["link_kind"] == "landing_page" for a in result["assets"])


def test_sync_schedule_prioritizes_critical_and_backs_off_failures():
    urgent = next_sync({**ENTRY, "priority": "critical"})
    long_tail = next_sync({**ENTRY, "priority": "long_tail"})
    failed = next_sync(ENTRY, 3)
    assert urgent["next_attempt_at"] < long_tail["next_attempt_at"]
    assert failed["failures"] == 3
    assert not sync_due({"_sync": urgent})
    assert sync_due({})
