from __future__ import annotations

import re
from pathlib import Path


WORKFLOW = Path(".github/workflows/sync.yml")
PYTHON_LINT_TEST_ACTION = Path(".github/actions/python-lint-test/action.yml")
SCRIPTS_DIR = Path("scripts")


def test_deploy_job_has_secret_preflight():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "Validate deploy secrets" in workflow
    for name in (
        "ALIYUN_DEPLOY_KEY",
        "ALIYUN_HOST",
        "ALIYUN_USER",
        "ALIYUN_DEPLOY_PATH",
    ):
        assert name in workflow


def test_workflow_dispatch_exposes_sync_filters():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "only:" in workflow
    assert "skip:" in workflow
    assert "SYNC_ONLY: ${{ inputs.only }}" in workflow
    assert "SYNC_SKIP: ${{ inputs.skip }}" in workflow
    assert "python scripts/sync.py @cmdArgs" in workflow


def test_network_link_check_is_split_into_own_job():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "\n  link-check:" in workflow
    sync_job = workflow.split("\n  sync:", 1)[1].split("\n  link-check:", 1)[0]
    assert "python scripts/validate_links.py" not in sync_job
    assert "Upload link health artifact" in workflow


def test_link_check_writes_step_summary():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    link_job = workflow.split("\n  link-check:", 1)[1].split("\n  deploy:", 1)[0]

    assert "Write link health summary" in link_job
    assert "python scripts/link_health_summary.py data/link-health.json" in link_job


def test_link_check_uses_synced_latest_data_artifact():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    sync_job = workflow.split("\n  sync:", 1)[1].split("\n  link-check:", 1)[0]
    link_job = workflow.split("\n  link-check:", 1)[1].split("\n  deploy:", 1)[0]

    assert "Upload latest data artifact" in sync_job
    assert "name: latest-data" in sync_job
    assert "path: data/latest.json" in sync_job
    assert "Download latest data artifact" in link_job
    assert "name: latest-data" in link_job
    assert "path: data/" in link_job


def test_deploy_does_not_wait_for_link_check():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    deploy_job = workflow.split("\n  deploy:", 1)[1]

    assert "needs: sync" in deploy_job
    assert "needs: link-check" not in deploy_job


def test_python_lint_test_action_splits_test_steps():
    action = PYTHON_LINT_TEST_ACTION.read_text(encoding="utf-8")

    expected_steps = (
        "Test - config (validate_config)",
        "Test - schema (latest.json)",
        "Test - render (README)",
        "Test - web (build_web)",
        "Test - vendor (update_vendor)",
        "Test - links (validate_links)",
        "Test - sync core",
        "Test - http/net layer",
        "Test - fetchers",
        "Test - workflow.yml self-check",
    )
    for step in expected_steps:
        assert step in action


def test_scripts_with_non_ascii_print_reconfigure_stdio():
    """防止 Windows runner cp1252 编码崩溃的回归测试。

    任何 print 中文/emoji 的入口脚本都必须在最早机会
    reconfigure stdio 为 UTF-8，否则会被 'charmap' codec 拒绝。
    """
    print_non_ascii = re.compile(r"print\([^)]*[^\x00-\x7f]")
    has_reconfigure = re.compile(r"\.reconfigure\(.*encoding\s*=\s*['\"]utf-8['\"]")

    offenders: list[str] = []
    for path in SCRIPTS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if print_non_ascii.search(text) and not has_reconfigure.search(text):
            offenders.append(str(path))

    assert not offenders, (
        f"以下脚本 print 了非 ASCII 字符但缺少 stdio UTF-8 reconfigure，"
        f"会在 Windows runner 上崩溃：{offenders}"
    )
