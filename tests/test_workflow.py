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


def test_publication_uses_only_validated_data_and_both_editions():
    import yaml

    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    assert jobs["link-check"]["needs"] == "sync-merge"
    assert jobs["publish"]["needs"] == "link-check"
    assert "python scripts/validate_links.py --gate" in str(jobs["link-check"])
    assert "candidate-data" in str(jobs["sync-merge"])
    assert "validated-data" in str(jobs["link-check"])
    assert "validated-data" in str(jobs["publish"])
    assert "dist-cn" in str(jobs["publish"]) and "dist-intl" in str(jobs["publish"])
    assert "Commit verified snapshot" in str(jobs["publish"])
    assert "git-auto-commit" not in str(jobs["sync-merge"])


def test_deploys_pin_source_data_and_frontend_to_same_successful_run():
    for path in (DEPLOY_INTL, DEPLOY_CN):
        workflow = path.read_text(encoding="utf-8")
        assert 'workflows: ["Sync Latest Software"]' in workflow
        assert "github.event.workflow_run.conclusion == 'success'" in workflow
        assert "ref: ${{ steps.release.outputs.sha }}" in workflow
        assert workflow.count("run-id: ${{ steps.release.outputs.run_id }}") == 2
        assert "name: validated-data" in workflow
        assert "python scripts/build_web.py" not in workflow
        assert "  push:" not in workflow


def test_sync_filters_are_applied_before_partitioning_and_windows_fetcher_runs_on_windows():
    import yaml

    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    assert jobs["sync"]["runs-on"] == "windows-latest"
    assert '--only "$SYNC_ONLY" --skip "$SYNC_SKIP"' in str(jobs["generate-shards"])
    assert 'ARGS+=(--only "$SYNC_ONLY")' not in str(jobs["sync"])


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


def test_sync_shard_uses_github_etag_cache():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    sync_job = workflow.split("\n  sync:", 1)[1].split("\n  sync-merge:", 1)[0]

    assert "LATEST_SOFTWARES_HTTP_CACHE:" in sync_job
    assert "actions/cache/restore@" in sync_job
    assert "actions/cache/save@" in sync_job


def test_pr_checks_cover_dependency_update_prs():
    """Dependabot 的 npm / Actions / 依赖升级 PR 必须触发 pr-checks 并真正跑前端构建。"""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    pr_trigger = workflow.split("\n  pull_request:", 1)[1].split("\npermissions:", 1)[0]
    for path in (
        "'requirements*.txt'",
        "'pyproject.toml'",
        "'package.json'",
        "'package-lock.json'",
        "'.pre-commit-config.yaml'",
        "'.github/**'",
    ):
        assert path in pr_trigger, path

    pr_job = workflow.split("\n  pr-checks:", 1)[1].split("\n  generate-shards:", 1)[0]
    assert "actions/setup-node@" in pr_job
    assert "npm ci" in pr_job
    assert "npm run build" in pr_job


def test_workflows_install_python_deps_with_uv():
    for path in (WORKFLOW, DEPLOY_INTL):
        workflow = path.read_text(encoding="utf-8")
        assert "astral-sh/setup-uv@" in workflow, path
        assert "cache: 'pip'" not in workflow, path
        assert re.search(r"^\s*run: pip install", workflow, re.M) is None, path
