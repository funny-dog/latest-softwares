from __future__ import annotations

from scripts.discover.models import Candidate, PLACEHOLDER_DESC_CN


def test_candidate_homepage_derived_from_repo():
    c = Candidate(
        repo="pbatard/rufus", name="rufus", stars=29000, description="USB tool"
    )
    assert c.homepage == "https://github.com/pbatard/rufus"
    assert PLACEHOLDER_DESC_CN.startswith("TODO")
