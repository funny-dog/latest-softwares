from __future__ import annotations

from scripts.discover.categorize import categorize


def test_browser_keyword():
    assert categorize(["browser", "web"], "A privacy browser") == "Browsers"


def test_dev_tools_keyword():
    assert (
        categorize(["cli", "git"], "Developer command-line tool") == "Developer Tools"
    )


def test_ai_keyword():
    assert categorize([], "Local LLM inference engine") == "AI Tools"


def test_fallback_to_utilities():
    assert categorize([], "Some unclassifiable thing") == "Utilities"
