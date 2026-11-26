from __future__ import annotations

from scripts.dependabot_auto_merge import (
    evaluate_pr_for_auto_merge,
    parse_dependabot_updates,
)


def _sample_pr(**overrides: object) -> dict:
    base = {
        "number": 29,
        "title": "chore(deps): bump the python-minor-patch group with 4 updates",
        "state": "OPEN",
        "isDraft": False,
        "baseRefName": "main",
        "headRefOid": "abc123",
        "mergeable": "MERGEABLE",
        "author": {"login": "app/dependabot"},
        "statusCheckRollup": [
            {"name": "pr-checks", "status": "COMPLETED", "conclusion": "SUCCESS"},
            {"name": "sync", "status": "COMPLETED", "conclusion": "SKIPPED"},
        ],
    }
    base.update(overrides)
    return base


def test_parse_dependabot_updates_extracts_minor_and_major():
    msg_minor = """chore(deps): bump fastapi

---
updated-dependencies:
- dependency-name: fastapi
  dependency-version: 0.162.0
  dependency-type: direct:production
  update-type: version-update:semver-minor
  dependency-group: python-minor-patch
...

Signed-off-by: dependabot[bot] <support@github.com>
"""
    msg_major = """chore(ci): bump actions

---
updated-dependencies:
- dependency-name: cloudflare/wrangler-action
  dependency-version: '4'
  update-type: version-update:semver-major
...
"""
    assert parse_dependabot_updates([msg_minor]) == [
        {"dependency-name": "fastapi", "update-type": "version-update:semver-minor"}
    ]
    assert parse_dependabot_updates([msg_minor, msg_major]) == [
        {"dependency-name": "fastapi", "update-type": "version-update:semver-minor"},
        {
            "dependency-name": "cloudflare/wrangler-action",
            "update-type": "version-update:semver-major",
        },
    ]


def test_evaluate_pr_allows_verified_dependabot_minor_patch():
    pr = _sample_pr()
    updates = [
        {"dependency-name": "fastapi", "update-type": "version-update:semver-minor"},
        {
            "dependency-name": "types-requests",
            "update-type": "version-update:semver-patch",
        },
    ]
    ok, reason = evaluate_pr_for_auto_merge(pr, updates)
    assert ok is True
    assert "fastapi" in reason


def test_evaluate_pr_rejects_major_update():
    pr = _sample_pr()
    updates = [
        {
            "dependency-name": "cloudflare/wrangler-action",
            "update-type": "version-update:semver-major",
        }
    ]
    ok, reason = evaluate_pr_for_auto_merge(pr, updates)
    assert ok is False
    assert "semver-major" in reason


def test_evaluate_pr_rejects_non_dependabot_author():
    pr = _sample_pr(author={"login": "github-actions[bot]"})
    updates = [
        {"dependency-name": "fastapi", "update-type": "version-update:semver-minor"}
    ]
    ok, _ = evaluate_pr_for_auto_merge(pr, updates)
    assert ok is False


def test_evaluate_pr_rejects_missing_or_failed_checks():
    pr_no_checks = _sample_pr(statusCheckRollup=[])
    updates = [
        {"dependency-name": "fastapi", "update-type": "version-update:semver-minor"}
    ]
    ok, _ = evaluate_pr_for_auto_merge(pr_no_checks, updates)
    assert ok is False

    pr_failed = _sample_pr(
        statusCheckRollup=[
            {"name": "pr-checks", "status": "COMPLETED", "conclusion": "FAILURE"}
        ]
    )
    ok, _ = evaluate_pr_for_auto_merge(pr_failed, updates)
    assert ok is False


def test_evaluate_pr_rejects_conflicting_or_missing_metadata():
    updates = [
        {"dependency-name": "fastapi", "update-type": "version-update:semver-minor"}
    ]
    assert (
        evaluate_pr_for_auto_merge(_sample_pr(mergeable="CONFLICTING"), updates)[0]
        is False
    )
    assert evaluate_pr_for_auto_merge(_sample_pr(), [])[0] is False
