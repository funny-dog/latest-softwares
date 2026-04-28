from __future__ import annotations

from scripts.editions import filter_data_by_edition


def test_filter_data_by_edition_filters_packages_and_stats():
    data = {
        "schema_version": 2,
        "packages": [
            {"id": "cn", "editions": ["cn"], "_stale": True},
            {"id": "intl", "editions": ["intl"]},
            {"id": "both", "editions": ["cn", "intl"]},
        ],
        "stats": {
            "total": 3,
            "success": 1,
            "failed": 2,
            "failed_ids": ["cn", "missing"],
            "failures": [
                {"id": "cn", "error": "cn failure"},
                {"id": "missing", "error": "not emitted"},
            ],
        },
    }

    filtered = filter_data_by_edition(data, "intl")

    assert [pkg["id"] for pkg in filtered["packages"]] == ["intl", "both"]
    assert filtered["edition"] == "intl"
    assert filtered["stats"] == {
        "total": 2,
        "success": 2,
        "failed": 0,
        "failed_ids": [],
    }
