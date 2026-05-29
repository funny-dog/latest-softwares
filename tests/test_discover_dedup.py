from __future__ import annotations

from scripts.discover import dedup
from scripts.discover.models import Candidate


def test_is_new_false_for_existing_repo(monkeypatch):
    fake_cfg = {
        "packages": [
            {
                "id": "rufus",
                "fetcher": "github_release",
                "args": {"repo": "pbatard/rufus"},
            },
        ]
    }
    monkeypatch.setattr(dedup, "load_packages_config", lambda: fake_cfg)
    existing = dedup.existing_repos()
    c = Candidate(repo="pbatard/rufus", name="rufus", stars=1, description="")
    assert dedup.is_new(c, existing) is False


def test_is_new_true_for_unknown_repo(monkeypatch):
    fake_cfg = {
        "packages": [
            {
                "id": "rufus",
                "fetcher": "github_release",
                "args": {"repo": "pbatard/rufus"},
            },
        ]
    }
    monkeypatch.setattr(dedup, "load_packages_config", lambda: fake_cfg)
    existing = dedup.existing_repos()
    c = Candidate(repo="zen-browser/desktop", name="zen", stars=1, description="")
    assert dedup.is_new(c, existing) is True


def test_repo_match_is_case_insensitive(monkeypatch):
    fake_cfg = {
        "packages": [
            {"id": "x", "fetcher": "github_release", "args": {"repo": "PBatard/Rufus"}},
        ]
    }
    monkeypatch.setattr(dedup, "load_packages_config", lambda: fake_cfg)
    existing = dedup.existing_repos()
    c = Candidate(repo="pbatard/rufus", name="rufus", stars=1, description="")
    assert dedup.is_new(c, existing) is False
