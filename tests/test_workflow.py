from __future__ import annotations

import re
from pathlib import Path


WORKFLOW = Path(".github/workflows/sync.yml")
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
