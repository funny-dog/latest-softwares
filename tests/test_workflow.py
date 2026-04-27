from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/sync.yml")


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
