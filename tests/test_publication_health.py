from datetime import datetime, timedelta, timezone

import pytest

from scripts.check_publication_health import check_publication, main


@pytest.mark.parametrize("age,code", [(6, 0), (24, 0), (25, 1), (-1, 1)])
def test_publication_age_is_bounded(age, code):
    now = datetime(2026, 10, 23, tzinfo=timezone.utc)
    data = {
        "release_id": "snapshot",
        "verified_at": (now - timedelta(hours=age)).isoformat(),
    }
    result, message = check_publication(data, now, 24)
    assert result == code
    assert "snapshot" in message and f"age={age:.1f}h" in message


def test_missing_verification_fails_and_writes_summary(tmp_path, monkeypatch):
    data = tmp_path / "latest.json"
    data.write_text("{}")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(["--data", str(data)]) == 1
    assert "No verified publication snapshot" in summary.read_text()
