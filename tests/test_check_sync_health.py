# tests/test_check_sync_health.py
from __future__ import annotations

import json
from scripts.check_sync_health import check_sync_health


def test_check_sync_health_pass(tmp_path):
    """失败率低于阈值时应通过"""
    log_file = tmp_path / "sync_errors.jsonl"
    # 写入 10 条记录，1 条失败（10%）
    entries = [{"id": f"pkg{i}", "status": "ok"} for i in range(9)]
    entries.append({"id": "pkg9", "status": "fail", "error": "timeout"})
    with open(log_file, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    result = check_sync_health(log_file, max_fail_rate=0.10)
    assert result is True


def test_check_sync_health_fail(tmp_path):
    """失败率高于阈值时应失败"""
    log_file = tmp_path / "sync_errors.jsonl"
    # 写入 10 条记录，2 条失败（20%）
    entries = [{"id": f"pkg{i}", "status": "ok"} for i in range(8)]
    entries.append({"id": "pkg8", "status": "fail", "error": "timeout"})
    entries.append({"id": "pkg9", "status": "fail", "error": "404"})
    with open(log_file, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    result = check_sync_health(log_file, max_fail_rate=0.10)
    assert result is False


def test_check_sync_health_empty_file(tmp_path):
    """空日志文件应通过"""
    log_file = tmp_path / "sync_errors.jsonl"
    log_file.touch()

    result = check_sync_health(log_file, max_fail_rate=0.10)
    assert result is True


def test_check_sync_health_no_file(tmp_path):
    """日志文件不存在时应通过"""
    log_file = tmp_path / "sync_errors.jsonl"

    result = check_sync_health(log_file, max_fail_rate=0.10)
    assert result is True
