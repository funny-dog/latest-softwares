from __future__ import annotations

import re
from pathlib import Path


WORKFLOW = Path(".github/workflows/sync.yml")
DEPLOY_INTL = Path(".github/workflows/deploy.yml")
DEPLOY_CN = Path(".github/workflows/deploy-cn.yml")
PYTHON_LINT_TEST_ACTION = Path(".github/actions/python-lint-test/action.yml")
SCRIPTS_DIR = Path("scripts")


def test_deploy_job_has_secret_preflight():
    """国内版(阿里云)部署前必须 fail-fast 校验 secret —— 部署拆分后位于 deploy-cn.yml。"""
    workflow = DEPLOY_CN.read_text(encoding="utf-8")

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
    assert "python scripts/sync.py" in workflow


def test_network_link_check_is_split_into_own_job():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "\n  link-check:" in workflow
    sync_job = workflow.split("\n  sync:", 1)[1].split("\n  link-check:", 1)[0]
    assert "python scripts/validate_links.py" not in sync_job
    assert "Upload link health artifact" in workflow


def test_link_check_writes_step_summary():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    # link-check 现为 sync.yml 最后一个 job（deploy 已拆出），取其到文件末尾即可。
    link_job = workflow.split("\n  link-check:", 1)[1]

    assert "Write link health summary" in link_job
    assert "python scripts/link_health_summary.py data/link-health.json" in link_job


def test_link_check_uses_synced_latest_data_artifact():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    sync_job = workflow.split("\n  sync:", 1)[1].split("\n  link-check:", 1)[0]
    link_job = workflow.split("\n  link-check:", 1)[1]

    assert "Upload latest data artifact" in sync_job
    assert "name: latest-data" in sync_job
    assert "path: data/latest.json" in sync_job
    assert "Download latest data artifact" in link_job
    assert "name: latest-data" in link_job
    assert "path: data/" in link_job


def test_deploy_does_not_wait_for_link_check():
    """部署拆分为独立 workflow 后,应在 Sync 成功后接力触发(workflow_run),
    而不被 flaky 的 link-check 阻塞 —— 两版 deploy 都不应引用 link-check。

    拆分前由 `needs: sync` + 不写 `needs: link-check` 表达此意图;拆分后等价于
    `workflow_run: workflows: ["Sync Latest Software"]`(接力 Sync)且全文不提 link-check。
    """
    for path in (DEPLOY_INTL, DEPLOY_CN):
        workflow = path.read_text(encoding="utf-8")
        # 接力 Sync 完成后部署最新数据（替代拆分前的 needs: sync）
        assert 'workflows: ["Sync Latest Software"]' in workflow, path
        # 不依赖、也不等待 link-check
        assert "link-check" not in workflow, path


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
