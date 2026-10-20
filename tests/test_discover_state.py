from __future__ import annotations

from pathlib import Path
from scripts.discover.state import DiscoveryState


def test_discovery_state_save_and_load(tmp_path: Path):
    state_file = tmp_path / "state.json"
    state = DiscoveryState()
    state.update_cursor("github", {"page": 3, "min_stars": 6000})
    state.rejected.append("rejected-app")
    state.record_retry("owner/repo-fail", "timed out")

    state.save(state_file)
    assert state_file.is_file()

    loaded = DiscoveryState.load(state_file)
    assert loaded.get_cursor("github") == {"page": 3, "min_stars": 6000}
    assert loaded.is_rejected("rejected-app") is True
    assert loaded.is_rejected("other-app") is False
    assert "owner/repo-fail" in loaded.retries
    assert loaded.retries["owner/repo-fail"]["retry_count"] == 1

    # 重试成功后清除记录
    loaded.record_success("owner/repo-fail")
    assert "owner/repo-fail" not in loaded.retries


def test_discovery_state_load_non_existent(tmp_path: Path):
    non_existent = tmp_path / "does_not_exist.json"
    state = DiscoveryState.load(non_existent)
    assert state.version == 1
    assert state.rejected == []
